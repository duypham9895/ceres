"""Crawler agent for fetching bank loan pages with retry and anti-bot detection."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot
from ceres.database import Database
from ceres.utils.captcha import CaptchaSolver, create_captcha_solver
from ceres.utils.rate_limiter import RateLimiter

DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_CONCURRENCY = 5
PAGE_TIMEOUT_MS = 30_000
BACKOFF_BASE_S = 1.0


class CrawlerAgent(BaseAgent):
    """Agent that crawls bank loan pages with retry, rate limiting, and anti-bot detection.

    Each bank crawl uses a local RateLimiter instance for concurrency safety.
    Banks are crawled concurrently up to max_concurrency via asyncio.Semaphore.
    """

    name: str = "crawler"

    def __init__(
        self,
        db: Database,
        config: Optional[Any] = None,
        browser_manager: Optional[BrowserManager] = None,
    ) -> None:
        super().__init__(db=db, config=config)
        self._max_retries: int = getattr(config, "max_retries", DEFAULT_MAX_RETRIES)
        self._max_concurrency: int = getattr(
            config, "max_concurrency", DEFAULT_MAX_CONCURRENCY
        )
        self._browser_manager = browser_manager
        self._owns_browser = False
        self._captcha_solver: CaptchaSolver = create_captcha_solver()

    async def run(self, **kwargs) -> dict:
        """Crawl active bank strategies.

        Args:
            bank_code: Optional filter to crawl only a specific bank.

        Returns:
            Stats dict with banks_crawled, pages_fetched, and failures counts.
        """
        bank_code: Optional[str] = kwargs.get("bank_code")
        strategies = await self.db.fetch_active_strategies()

        if bank_code is not None:
            strategies = [s for s in strategies if s["bank_code"] == bank_code]

        # If no shared browser manager was injected, create one for this run
        if self._browser_manager is None:
            self._browser_manager = BrowserManager(
                max_contexts=self._max_concurrency,
            )
            self._owns_browser = True

        try:
            semaphore = asyncio.Semaphore(self._max_concurrency)
            stats = {"banks_crawled": 0, "pages_fetched": 0, "failures": 0}

            async def _bounded_crawl(strategy: dict) -> dict:
                async with semaphore:
                    return await self._crawl_bank(strategy)

            results = await asyncio.gather(
                *(_bounded_crawl(s) for s in strategies),
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, BaseException):
                    self.logger.error(f"Bank crawl failed: {result}")
                    stats["failures"] += 1
                else:
                    stats["banks_crawled"] += result["banks_crawled"]
                    stats["pages_fetched"] += result["pages_fetched"]
                    stats["failures"] += result["failures"]

            self.logger.info(
                f"Crawl complete: {stats['banks_crawled']} banks, "
                f"{stats['pages_fetched']} pages, {stats['failures']} failures"
            )
            return stats
        finally:
            if self._owns_browser and self._browser_manager is not None:
                await self._browser_manager.stop()
                self._browser_manager = None
                self._owns_browser = False

    async def _crawl_bank(self, strategy: dict) -> dict:
        """Crawl all loan pages for a single bank strategy.

        Creates a local RateLimiter per bank for concurrency safety.
        The crawl_log lifecycle is wrapped in try/finally to ensure
        orphaned 'running' logs are always cleaned up on crash.
        """
        bank_code = strategy["bank_code"]
        strategy_id = strategy["id"]
        loan_page_urls: list[str] = json.loads(strategy["loan_page_urls"])
        rate_limiter = RateLimiter(delay_ms=strategy["rate_limit_ms"])

        log_row = await self.db.create_crawl_log(
            bank_id=str(strategy["bank_id"]),
            strategy_id=str(strategy_id),
            status="running",
        )
        crawl_log_id = str(log_row["id"])

        bank_stats = {"banks_crawled": 0, "pages_fetched": 0, "failures": 0}
        anti_bot_detected = False
        last_error: Optional[str] = None

        try:
            for url in loan_page_urls:
                try:
                    html = await self._fetch_with_retry(
                        url=url,
                        strategy=strategy,
                        bank_code=bank_code,
                        rate_limiter=rate_limiter,
                    )

                    bot_result = detect_anti_bot(html)
                    if bot_result.detected:
                        # Attempt captcha solving if a solver is configured
                        solved = False
                        if bot_result.anti_bot_type and "captcha" in bot_result.anti_bot_type.lower():
                            self.logger.info(
                                "Captcha detected on %s, attempting solve", url,
                            )
                            token = await self._captcha_solver.solve(
                                challenge_type="recaptcha_v2",
                                page_url=url,
                                sitekey=bot_result.details or "",
                            )
                            if token:
                                self.logger.info("Captcha solved for %s, re-fetching", url)
                                try:
                                    html = await self._fetch_with_retry(
                                        url=url,
                                        strategy=strategy,
                                        bank_code=bank_code,
                                        rate_limiter=rate_limiter,
                                    )
                                    recheck = detect_anti_bot(html)
                                    if not recheck.detected:
                                        solved = True
                                except Exception as captcha_exc:
                                    self.logger.warning(
                                        "Re-fetch after captcha solve failed for %s: %s",
                                        url, captcha_exc,
                                    )

                        if not solved:
                            anti_bot_detected = True
                            self.logger.warning(
                                f"Anti-bot BLOCKED {url}: {bot_result.anti_bot_type} — skipping storage"
                            )
                            bank_stats["failures"] += 1
                            last_error = f"{url}: blocked by {bot_result.anti_bot_type}"
                            continue

                    await self.db.store_raw_html(
                        crawl_log_id=crawl_log_id,
                        bank_id=str(strategy["bank_id"]),
                        page_url=url,
                        raw_html=html,
                    )
                    bank_stats["pages_fetched"] += 1

                except Exception as exc:
                    self.logger.error(f"Failed to crawl {url}: {exc}")
                    bank_stats["failures"] += 1
                    last_error = f"{url}: {exc}"

            if bank_stats["failures"] == 0:
                status = "success"
            elif bank_stats["pages_fetched"] > 0:
                status = "partial"
            else:
                status = "failed"
            if bank_stats["pages_fetched"] > 0:
                bank_stats["banks_crawled"] = 1
            error_info: dict = {}
            if last_error and status == "failed":
                error_info = {
                    "error_type": "CrawlError",
                    "error_message": last_error[:500],
                }
        except BaseException as exc:
            status = "failed"
            error_info = {
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
            }
            self.logger.exception(f"Crawl crashed for {bank_code}")

        try:
            await self.db.update_crawl_log(
                crawl_log_id=crawl_log_id,
                status=status,
                pages_crawled=bank_stats["pages_fetched"],
                **error_info,
            )
            await self.db.update_strategy_success_rate(
                strategy_id=str(strategy_id),
            )
        except Exception:
            self.logger.exception(
                f"Failed to update crawl_log {crawl_log_id} to {status}"
            )

        return bank_stats

    async def _fetch_with_retry(
        self,
        url: str,
        strategy: dict,
        bank_code: str,
        rate_limiter: RateLimiter,
    ) -> str:
        """Fetch a page with exponential backoff retries.

        Raises the last exception if all retries are exhausted.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(self._max_retries):
            try:
                await rate_limiter.wait(domain=bank_code)
                return await self._fetch_page(url, strategy)
            except Exception as exc:
                last_exc = exc
                self.logger.warning(
                    f"Fetch attempt {attempt + 1}/{self._max_retries} "
                    f"failed for {url}: {exc}"
                )
                if attempt < self._max_retries - 1:
                    backoff = BACKOFF_BASE_S * (2 ** attempt)
                    await asyncio.sleep(backoff)

        raise last_exc  # type: ignore[misc]

    async def _fetch_page(self, url: str, strategy: dict) -> str:
        """Fetch a single page using the shared browser manager.

        Acquires a context slot (semaphore-gated), navigates, extracts HTML,
        and releases the slot. Each page gets its own lightweight context
        to isolate cookies/state between pages.
        """
        bypass = strategy.get("bypass_method", "headless_browser")
        browser_type = (
            BrowserType.UNDETECTED
            if bypass in {"undetected", "undetected_chrome"}
            else BrowserType.PLAYWRIGHT
        )

        context, page = await self._browser_manager.create_context(
            browser_type=browser_type,
        )
        try:
            if browser_type == BrowserType.PLAYWRIGHT:
                await page.goto(
                    url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS,
                )
                try:
                    await page.wait_for_selector(
                        "table, .product, .loan, [class*='rate'], [class*='bunga']",
                        timeout=5000,
                    )
                except Exception:
                    pass  # Timeout is OK, content might be in static HTML
                html = await page.content()
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, page.get, url)
                html = await loop.run_in_executor(
                    None, lambda: page.page_source or ""
                )
            return html
        finally:
            await self._browser_manager.close_context(context, browser_type)

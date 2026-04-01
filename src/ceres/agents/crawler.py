"""Crawler agent for fetching bank loan pages with retry and anti-bot detection."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot
from ceres.database import Database
from ceres.utils.rate_limiter import RateLimiter

DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_CONCURRENCY = 5
BACKOFF_BASE_S = 1.0


class CrawlerAgent(BaseAgent):
    """Agent that crawls bank loan pages with retry, rate limiting, and anti-bot detection.

    Each bank crawl uses a local RateLimiter instance for concurrency safety.
    Banks are crawled concurrently up to max_concurrency via asyncio.Semaphore.
    """

    name: str = "crawler"

    def __init__(self, db: Database, config: Optional[Any] = None) -> None:
        super().__init__(db=db, config=config)
        self._max_retries: int = getattr(config, "max_retries", DEFAULT_MAX_RETRIES)
        self._max_concurrency: int = getattr(
            config, "max_concurrency", DEFAULT_MAX_CONCURRENCY
        )

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
            if isinstance(result, Exception):
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

    async def _crawl_bank(self, strategy: dict) -> dict:
        """Crawl all loan pages for a single bank strategy.

        Creates a local RateLimiter per bank for concurrency safety.
        """
        bank_code = strategy["bank_code"]
        strategy_id = strategy["id"]
        loan_page_urls: list[str] = json.loads(strategy["loan_page_urls"])
        rate_limiter = RateLimiter(delay_ms=strategy["rate_limit_ms"])

        log_id = await self.db.create_crawl_log(
            strategy_id=strategy_id,
            bank_code=bank_code,
            status="running",
        )

        bank_stats = {"banks_crawled": 0, "pages_fetched": 0, "failures": 0}
        anti_bot_detected = False

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
                    anti_bot_detected = True
                    self.logger.warning(
                        f"Anti-bot detected on {url}: {bot_result.anti_bot_type}"
                    )

                await self.db.store_raw_html(
                    strategy_id=strategy_id,
                    url=url,
                    html=html,
                    bank_code=bank_code,
                )
                bank_stats["pages_fetched"] += 1

            except Exception as exc:
                self.logger.error(f"Failed to crawl {url}: {exc}")
                bank_stats["failures"] += 1

        status = "failed" if bank_stats["failures"] > 0 else "completed"
        if bank_stats["pages_fetched"] > 0:
            bank_stats["banks_crawled"] = 1

        await self.db.update_crawl_log(
            log_id=log_id,
            status=status,
            pages_fetched=bank_stats["pages_fetched"],
            anti_bot_detected=anti_bot_detected,
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
        """Fetch a single page using the browser manager.

        Chooses BrowserType based on the strategy's bypass_method.
        Returns the page HTML content.
        """
        bypass = strategy.get("bypass_method", "headless_browser")
        browser_type = (
            BrowserType.UNDETECTED
            if bypass == "undetected"
            else BrowserType.PLAYWRIGHT
        )

        manager = BrowserManager()
        browser, page = await manager.create_context(browser_type=browser_type)
        try:
            if browser_type == BrowserType.PLAYWRIGHT:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                html = await page.content()
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, page.get, url)
                html = await loop.run_in_executor(
                    None, getattr(page, "page_source", lambda: "")
                )
            return html
        finally:
            await manager.close_context(browser, browser_type)

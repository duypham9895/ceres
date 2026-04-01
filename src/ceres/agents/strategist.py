"""Strategist agent for anti-bot detection and loan URL discovery."""

from __future__ import annotations

from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.stealth import detect_anti_bot
from ceres.database import Database

COMMON_LOAN_PATHS = [
    "/kpr",
    "/kredit",
    "/pinjaman",
    "/loan",
    "/mortgage",
    "/kredit-pemilikan-rumah",
    "/produk/kredit",
    "/produk/pinjaman",
    "/personal/kredit",
    "/personal/pinjaman",
    "/consumer-loan",
    "/kpa",
    "/kpt",
    "/multiguna",
    "/kredit-multiguna",
    "/kendaraan",
    "/kredit-kendaraan",
]

_LOAN_KEYWORDS = {"kredit", "pinjaman", "kpr", "loan", "bunga", "angsuran", "tenor"}

_VALID_WEBSITE_STATUSES = ("active", "unknown")

_DEFAULT_RATE_LIMIT_MS = 2000


class StrategistAgent(BaseAgent):
    """Analyzes bank websites for anti-bot measures and discovers loan URLs."""

    name: str = "strategist"

    def __init__(
        self, db: Database, config: Optional[Any] = None
    ) -> None:
        super().__init__(db=db, config=config)

    async def run(self, **kwargs: Any) -> dict:
        """Create scraping strategies for bank websites.

        Args:
            bank_code: Optional bank code to filter by.
            force: If True, recreate strategies even when active ones exist.

        Returns:
            Dict with strategies_created, strategies_updated, and errors counts.
        """
        bank_code: str | None = kwargs.get("bank_code")
        force: bool = kwargs.get("force", False)

        banks = await self.db.fetch_banks()
        if bank_code:
            banks = [b for b in banks if b.get("bank_code") == bank_code]

        active_strategies = await self.db.fetch_active_strategies()
        active_bank_ids = {s["bank_id"] for s in active_strategies}

        strategies_created = 0
        strategies_updated = 0
        errors = 0

        for bank in banks:
            if bank.get("website_status") not in _VALID_WEBSITE_STATUSES:
                continue

            has_existing = bank["id"] in active_bank_ids
            if has_existing and not force:
                continue

            try:
                analysis = await self._analyze_bank(bank)
            except Exception:
                self.logger.exception(
                    "Failed to analyze bank %s", bank.get("bank_code")
                )
                errors += 1
                continue

            strategy_data = {
                "bank_id": bank["id"],
                "bypass_method": analysis["bypass_method"],
                "anti_bot_detected": analysis["anti_bot_detected"],
                "anti_bot_type": analysis["anti_bot_type"],
                "loan_page_urls": analysis["loan_page_urls"],
                "selectors": analysis["selectors"],
                "rate_limit_ms": analysis["rate_limit_ms"],
            }

            await self.db.upsert_strategy(strategy_data)

            if has_existing:
                strategies_updated += 1
            else:
                strategies_created += 1

        return {
            "strategies_created": strategies_created,
            "strategies_updated": strategies_updated,
            "errors": errors,
        }

    async def _analyze_bank(self, bank: dict) -> dict:
        """Analyze a bank website for anti-bot measures and loan URLs.

        Launches a browser, navigates to the bank homepage, detects
        anti-bot measures, determines bypass method, and discovers
        loan-related URLs.
        """
        from ceres.browser.manager import BrowserManager, BrowserType

        browser_manager = BrowserManager()
        browser = None
        try:
            browser, page = await browser_manager.create_context(
                browser_type=BrowserType.PLAYWRIGHT
            )

            base_url = bank["website_url"].rstrip("/")
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)

            html = await page.content()
            anti_bot_result = detect_anti_bot(html)

            bypass_method = self._determine_bypass_method(
                bank, anti_bot_type=anti_bot_result.anti_bot_type
            )

            loan_urls = await self._discover_loan_urls(page, base_url)

            return {
                "anti_bot_detected": anti_bot_result.detected,
                "anti_bot_type": anti_bot_result.anti_bot_type,
                "bypass_method": bypass_method,
                "loan_page_urls": loan_urls,
                "selectors": {},
                "rate_limit_ms": _DEFAULT_RATE_LIMIT_MS,
            }
        finally:
            if browser is not None:
                await browser_manager.close_context(
                    browser, BrowserType.PLAYWRIGHT
                )

    def _determine_bypass_method(
        self, bank: dict, anti_bot_type: str | None
    ) -> str:
        """Determine the best bypass method based on bank and anti-bot info.

        Returns:
            One of "api", "undetected_chrome", or "headless_browser".
        """
        if bank.get("api_available"):
            return "api"

        if anti_bot_type == "fingerprint":
            return "undetected_chrome"

        return "headless_browser"

    async def _discover_loan_urls(
        self, page: Any, base_url: str
    ) -> list[str]:
        """Discover loan-related URLs by probing common paths.

        For each path in COMMON_LOAN_PATHS, navigates to base_url + path.
        If the response status is < 400 and the page contains loan keywords,
        the URL is included.

        Falls back to [base_url] if no loan URLs are found.
        """
        found_urls: list[str] = []

        for path in COMMON_LOAN_PATHS:
            url = f"{base_url}{path}"
            try:
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=15000
                )
                if response is None or response.status >= 400:
                    continue

                content = await page.content()
                content_lower = content.lower()

                if any(kw in content_lower for kw in _LOAN_KEYWORDS):
                    found_urls.append(url)
            except Exception:
                self.logger.debug("Failed to probe %s", url)
                continue

        if not found_urls:
            return [base_url]

        return found_urls

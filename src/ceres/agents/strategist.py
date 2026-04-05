"""Strategist agent for anti-bot detection and loan URL discovery."""

from __future__ import annotations

from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
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
        self._browser_manager: Optional[BrowserManager] = None
        self._owns_browser = False

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

        if self._browser_manager is None:
            self._browser_manager = BrowserManager(max_contexts=1)
            self._owns_browser = True

        try:
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

                await self.db.upsert_strategy(**strategy_data)

                if has_existing:
                    strategies_updated += 1
                else:
                    strategies_created += 1
        finally:
            if self._owns_browser and self._browser_manager is not None:
                await self._browser_manager.stop()
                self._browser_manager = None
                self._owns_browser = False

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
        if self._browser_manager is None:
            raise RuntimeError("BrowserManager not initialized")

        context = None
        try:
            context, page = await self._browser_manager.create_context(
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

            selectors = await self._discover_selectors(page, loan_urls)

            return {
                "anti_bot_detected": anti_bot_result.detected,
                "anti_bot_type": anti_bot_result.anti_bot_type,
                "bypass_method": bypass_method,
                "loan_page_urls": loan_urls,
                "selectors": selectors,
                "rate_limit_ms": _DEFAULT_RATE_LIMIT_MS,
            }
        finally:
            if context is not None:
                await self._browser_manager.close_context(
                    context, BrowserType.PLAYWRIGHT
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

    async def _discover_selectors(
        self, page: Any, loan_urls: list[str]
    ) -> dict:
        """Analyze loan page HTML to discover CSS selectors for data extraction.

        Navigates to the first loan URL and inspects the DOM for common
        patterns: tables with rate data, product cards, and loan info lists.
        Returns a selector config compatible with SelectorExtractor.
        """
        if not loan_urls:
            return {}

        url = loan_urls[0]
        try:
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            if response is None or response.status >= 400:
                return {}

            # Use JavaScript to inspect the DOM for common selector patterns
            selectors = await page.evaluate("""() => {
                const result = {container: null, fields: {}};

                // Strategy 1: Look for tables with rate/bunga keywords
                const tables = document.querySelectorAll('table');
                for (const table of tables) {
                    const text = table.textContent.toLowerCase();
                    if (text.includes('bunga') || text.includes('rate') || text.includes('suku')) {
                        const rows = table.querySelectorAll('tr');
                        if (rows.length > 1) {
                            result.container = 'table tr';
                            result.fields = {
                                name: 'td:first-child',
                                rate: 'td:nth-child(2)',
                                tenure: 'td:nth-child(3)',
                                amount: 'td:nth-child(4)',
                            };
                            return result;
                        }
                    }
                }

                // Strategy 2: Look for product card patterns
                const cardSelectors = [
                    '.product-card', '.loan-card', '.card-product',
                    '[class*="product"]', '[class*="loan-item"]',
                    '.produk', '[class*="kredit"]',
                ];
                for (const sel of cardSelectors) {
                    const cards = document.querySelectorAll(sel);
                    if (cards.length >= 2) {
                        result.container = sel;
                        // Look for heading and rate-like elements inside first card
                        const card = cards[0];
                        const heading = card.querySelector('h2, h3, h4, .title, .name, strong');
                        const rateEl = card.querySelector('[class*="rate"], [class*="bunga"], .rate, .interest');
                        if (heading) result.fields.name = heading.tagName.toLowerCase();
                        if (rateEl) result.fields.rate = '.' + [...rateEl.classList].join('.');
                        return result;
                    }
                }

                // Strategy 3: Look for definition lists or labeled values
                const dls = document.querySelectorAll('dl');
                for (const dl of dls) {
                    const text = dl.textContent.toLowerCase();
                    if (text.includes('bunga') || text.includes('rate') || text.includes('tenor')) {
                        result.container = 'dl';
                        result.fields = {name: 'dt', rate: 'dd'};
                        return result;
                    }
                }

                return result;
            }""")

            if selectors and selectors.get("container") and selectors.get("fields"):
                return selectors

        except Exception:
            self.logger.debug("Failed to discover selectors from %s", url)

        return {}

    async def _discover_loan_urls(
        self, page: Any, base_url: str
    ) -> list[str]:
        """Discover loan-related URLs by probing common paths AND scanning page links.

        Strategy:
        1. Probe hardcoded COMMON_LOAN_PATHS
        2. Go back to homepage, scan all <a> links for loan keywords
        3. Deduplicate and return unique loan URLs
        Falls back to [base_url] if nothing is found.
        """
        found_urls: set[str] = set()

        # Phase 1: Probe common loan paths
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
                    found_urls.add(url)
            except Exception:
                self.logger.debug("Failed to probe %s", url)
                continue

        # Phase 2: Scan homepage links for loan-related URLs
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
            links = await page.evaluate("""(baseUrl) => {
                const loanPatterns = /\\b(kpr|kpa|kpt|kredit|pinjaman|loan|mortgage|multiguna|kendaraan|refinanc|take.?over|modal.?kerja|investasi)\\b/i;
                const excludePatterns = /\\b(simulasi|kalkulator|calculator|karir|career|investor|annual.?report|csr|tentang|about|contact|faq|syarat|ketentuan|privacy|sitemap)\\b/i;
                const seen = new Set();
                const results = [];

                for (const a of document.querySelectorAll('a[href]')) {
                    let href = a.href;
                    if (!href || href.startsWith('javascript:') || href.startsWith('#') || href.startsWith('mailto:')) continue;

                    // Must be same domain
                    try {
                        const url = new URL(href);
                        const base = new URL(baseUrl);
                        if (url.hostname !== base.hostname) continue;
                        href = url.origin + url.pathname;  // strip query/hash
                    } catch { continue; }

                    if (seen.has(href)) continue;
                    seen.add(href);

                    // Check both URL path and link text for loan keywords
                    const text = (a.textContent || '').trim();
                    const fullText = href.toLowerCase() + ' ' + text.toLowerCase();

                    if (loanPatterns.test(fullText) && !excludePatterns.test(fullText)) {
                        results.push(href);
                    }
                }
                return results;
            }""", base_url)

            for link in links[:20]:  # cap at 20 to avoid over-crawling
                if link not in found_urls:
                    found_urls.add(link)
        except Exception:
            self.logger.debug("Failed to scan homepage links for %s", base_url)

        if not found_urls:
            return [base_url]

        return sorted(found_urls)

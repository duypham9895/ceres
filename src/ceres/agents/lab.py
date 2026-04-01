"""Lab agent for testing strategy fixes with approach escalation."""

from __future__ import annotations

import json
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserType
from ceres.browser.stealth import detect_anti_bot
from ceres.database import Database

_FAILING_THRESHOLD = 0.3

_MIN_CONTENT_LENGTH = 1000

TEST_APPROACHES = [
    {
        "name": "undetected_chromedriver",
        "bypass_method": "undetected_chrome",
        "browser_type": BrowserType.UNDETECTED,
    },
    {
        "name": "mobile_user_agent",
        "bypass_method": "headless_browser",
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"
        ),
    },
    {
        "name": "increased_delay",
        "bypass_method": "headless_browser",
        "rate_limit_ms": 5000,
    },
    {
        "name": "proxy_rotation",
        "bypass_method": "proxy_pool",
        "requires_proxy": True,
    },
    {
        "name": "api_discovery",
        "bypass_method": "api",
        "check_api": True,
    },
]


def _is_failing(strategy: dict) -> bool:
    """Return True if strategy is considered failing."""
    return (
        strategy.get("success_rate", 0.0) < _FAILING_THRESHOLD
        or strategy.get("anti_bot_detected", False)
    )


def _parse_first_url(strategy: dict) -> str | None:
    """Extract the first loan page URL from a strategy."""
    raw = strategy.get("loan_page_urls", "[]")
    try:
        urls = json.loads(raw) if isinstance(raw, str) else raw
        return urls[0] if urls else None
    except (json.JSONDecodeError, IndexError, TypeError):
        return None


class LabAgent(BaseAgent):
    """Tests alternative scraping approaches for failing strategies.

    Iterates through ``TEST_APPROACHES`` sequentially for each failing
    strategy. When a successful approach is found, auto-applies the fix
    via ``upsert_strategy``. Strategies with no working fix are escalated.
    """

    name: str = "lab"

    def __init__(
        self, db: Database, config: Optional[Any] = None
    ) -> None:
        super().__init__(db=db, config=config)

    async def run(self, **kwargs: Any) -> dict:
        """Test alternative approaches for failing strategies.

        Args:
            bank_code: Optional bank code to filter strategies.

        Returns:
            Dict with tests_run, fixes_found, and escalated counts.
        """
        bank_code: str | None = kwargs.get("bank_code")

        strategies = await self.db.fetch_active_strategies()

        if bank_code:
            strategies = [
                s for s in strategies if s.get("bank_code") == bank_code
            ]

        failing = [s for s in strategies if _is_failing(s)]

        tests_run = 0
        fixes_found = 0
        escalated = 0

        for strategy in failing:
            fixed = await self._try_fixes(strategy)
            tests_run += fixed["tests_run"]
            if fixed["success"]:
                fixes_found += 1
            else:
                escalated += 1

        return {
            "tests_run": tests_run,
            "fixes_found": fixes_found,
            "escalated": escalated,
        }

    async def _try_fixes(self, strategy: dict) -> dict:
        """Try each approach for a single strategy.

        Returns:
            Dict with tests_run count and success boolean.
        """
        tests_run = 0

        for approach in TEST_APPROACHES:
            if approach.get("requires_proxy"):
                continue

            result = await self._test_approach(strategy, approach)
            tests_run += 1

            feedback_data = {
                "strategy_id": strategy["id"],
                "test_approach": approach["name"],
                "result": "success" if result["success"] else "failure",
            }
            await self.db.add_strategy_feedback(**feedback_data)

            if result["success"]:
                update_data = {
                    "bank_id": strategy["bank_id"],
                    "bypass_method": result.get(
                        "bypass_method", approach["bypass_method"]
                    ),
                    "anti_bot_detected": False,
                    "loan_page_urls": strategy.get("loan_page_urls", "[]"),
                    "selectors": strategy.get("selectors", "{}"),
                    "rate_limit_ms": approach.get(
                        "rate_limit_ms",
                        strategy.get("rate_limit_ms", 2000),
                    ),
                }
                await self.db.upsert_strategy(**update_data)
                return {"tests_run": tests_run, "success": True}

        return {"tests_run": tests_run, "success": False}

    async def _test_approach(
        self, strategy: dict, approach: dict
    ) -> dict:
        """Test a single approach against a strategy's first loan URL.

        Launches a browser, navigates to the URL, checks for anti-bot
        detection and content length. Success requires no anti-bot
        detection AND content longer than 1000 characters.

        Returns:
            Dict with ``success`` boolean and optional ``bypass_method``.
        """
        from ceres.browser.manager import BrowserManager

        url = _parse_first_url(strategy)
        if not url:
            return {"success": False}

        browser_type = approach.get("browser_type", BrowserType.PLAYWRIGHT)
        browser_manager = BrowserManager()
        browser = None

        try:
            browser, page = await browser_manager.create_context(
                browser_type=browser_type
            )

            if browser_type == BrowserType.PLAYWRIGHT:
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=30000
                )
                html = await page.content()
            else:
                page.get(url)
                html = page.page_source

            anti_bot = detect_anti_bot(html)
            success = not anti_bot.detected and len(html) > _MIN_CONTENT_LENGTH

            result: dict[str, Any] = {"success": success}
            if success:
                result["bypass_method"] = approach["bypass_method"]
            return result
        except Exception:
            self.logger.exception(
                "Error testing approach %s for strategy %s",
                approach["name"],
                strategy.get("id"),
            )
            return {"success": False}
        finally:
            if browser is not None:
                await browser_manager.close_context(browser, browser_type)

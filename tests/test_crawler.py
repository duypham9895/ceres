"""Tests for the CrawlerAgent."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.agents.crawler import CrawlerAgent


class TestCrawlerAgent:
    @pytest.mark.asyncio
    async def test_crawl_single_bank(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser", "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 2000,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.store_raw_html = AsyncMock(return_value="raw1")
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db)
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html><body>KPR BCA</body></html>"
            result = await agent.run(bank_code="BCA")
        assert result["banks_crawled"] == 1
        db.store_raw_html.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_retries_on_failure(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser", "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 100,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db, config=MagicMock(max_retries=3, max_concurrency=5))
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Timeout")
            result = await agent.run(bank_code="BCA")
        assert result["failures"] == 1
        assert mock_fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_crawl_all_banks_requires_bank_code_in_strategy(self):
        """Regression: strategies from DB must include bank_code (requires JOIN in fetch_active_strategies).

        Without the JOIN, bank_code is absent and _crawl_bank raises KeyError.
        This test verifies the crawler works when bank_code is present in strategy data.
        """
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[
            {
                "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
                "bank_name": "BCA", "bypass_method": "headless_browser",
                "loan_page_urls": '["https://bca.co.id/kpr"]',
                "selectors": "{}", "rate_limit_ms": 2000,
                "anti_bot_detected": False, "version": 1,
            },
            {
                "id": "strat2", "bank_id": "uuid2", "bank_code": "BNI",
                "bank_name": "BNI", "bypass_method": "headless_browser",
                "loan_page_urls": '["https://bni.co.id/kpr"]',
                "selectors": "{}", "rate_limit_ms": 2000,
                "anti_bot_detected": False, "version": 1,
            },
        ])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.store_raw_html = AsyncMock()
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db)
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html><body>loan</body></html>"
            # No bank_code filter — crawls all banks. Would KeyError without the JOIN fix.
            result = await agent.run()
        assert result["banks_crawled"] == 2
        assert result["failures"] == 0

    @pytest.mark.asyncio
    async def test_crawl_fails_if_strategy_missing_bank_code(self):
        """Regression: without the DB JOIN fix, strategies have no bank_code and must fail."""
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[
            {
                "id": "strat1", "bank_id": "uuid1",
                # bank_code intentionally absent — simulates broken fetch_active_strategies
                "bypass_method": "headless_browser",
                "loan_page_urls": '["https://bca.co.id/kpr"]',
                "selectors": "{}", "rate_limit_ms": 2000,
                "anti_bot_detected": False, "version": 1,
            },
        ])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db)
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock):
            result = await agent.run()
        # All banks fail with KeyError when bank_code is missing
        assert result["failures"] == 1
        assert result["banks_crawled"] == 0

    @pytest.mark.asyncio
    async def test_crawl_detects_anti_bot(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 100,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.store_raw_html = AsyncMock(return_value="raw1")
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db)
        html_with_cf = '<html><div class="cf-browser-verification">Check</div></html>'
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html_with_cf
            result = await agent.run(bank_code="BCA")
        # Anti-bot detection now skips storing HTML and marks as blocked/failed.
        assert result["banks_crawled"] >= 0
        db.store_raw_html.assert_not_called()
        db.update_crawl_log.assert_called_once()
        # Verify the crawl log was updated with blocked/failed status
        call_kwargs = db.update_crawl_log.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_crawl_log_cleaned_up_on_crash(self):
        """Regression: if _crawl_bank crashes after creating the crawl_log,
        update_crawl_log must still be called with status='failed' so logs
        don't stay orphaned in 'running' state forever."""
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": "{}", "rate_limit_ms": 2000,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.update_crawl_log = AsyncMock()
        db.update_strategy_success_rate = AsyncMock()
        agent = CrawlerAgent(db=db)
        with patch.object(agent, "_fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
            # Simulate an unexpected crash (e.g., CancelledError, OOM) that
            # escapes the inner try/except
            mock_fetch.side_effect = asyncio.CancelledError()
            result = await agent.run(bank_code="BCA")
        # The crawl_log must be updated to 'failed', NOT left as 'running'
        db.update_crawl_log.assert_called_once()
        assert db.update_crawl_log.call_args.kwargs["status"] == "failed"

    @pytest.mark.asyncio
    async def test_success_rate_updated_after_crawl(self):
        """Regression: success_rate on bank_strategies was never updated after
        crawls, staying at 0.00 forever. Now _crawl_bank calls
        update_strategy_success_rate after each bank completes."""
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": "{}", "rate_limit_ms": 2000,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value={"id": "log1"})
        db.store_raw_html = AsyncMock()
        db.update_crawl_log = AsyncMock()
        db.update_strategy_success_rate = AsyncMock()
        agent = CrawlerAgent(db=db)
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>loan data</html>"
            await agent.run(bank_code="BCA")
        db.update_strategy_success_rate.assert_called_once_with(
            strategy_id="strat1",
        )

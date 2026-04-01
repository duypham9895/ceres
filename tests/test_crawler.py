"""Tests for the CrawlerAgent."""

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
        db.create_crawl_log = AsyncMock(return_value="log1")
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
        db.create_crawl_log = AsyncMock(return_value="log1")
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db, config=MagicMock(max_retries=3, max_concurrency=5))
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Timeout")
            result = await agent.run(bank_code="BCA")
        assert result["failures"] == 1
        assert mock_fetch.call_count == 3

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
        db.create_crawl_log = AsyncMock(return_value="log1")
        db.store_raw_html = AsyncMock(return_value="raw1")
        db.update_crawl_log = AsyncMock()
        agent = CrawlerAgent(db=db)
        html_with_cf = '<html><div class="cf-browser-verification">Check</div></html>'
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html_with_cf
            result = await agent.run(bank_code="BCA")
        update_call = db.update_crawl_log.call_args
        assert update_call.kwargs.get("anti_bot_detected") is True

"""Tests for the Strategist agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.agents.strategist import StrategistAgent


class TestStrategistAgent:
    @pytest.mark.asyncio
    async def test_determine_bypass_method_api(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": True}
        method = agent._determine_bypass_method(bank, anti_bot_type=None)
        assert method == "api"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_cloudflare(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type="cloudflare")
        assert method == "headless_browser"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_fingerprint(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type="fingerprint")
        assert method == "undetected_chrome"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_datadome(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type="datadome")
        assert method == "headless_browser"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_default(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type=None)
        assert method == "headless_browser"

    @pytest.mark.asyncio
    async def test_run_creates_strategy(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "BCA",
                "website_url": "https://bca.co.id",
                "api_available": False,
                "website_status": "active",
            }
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.upsert_strategy = AsyncMock(
            return_value={"id": "strat1", "bank_id": "uuid1", "version": 1}
        )
        agent = StrategistAgent(db=db)
        with patch.object(
            agent, "_analyze_bank", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = {
                "anti_bot_detected": False,
                "anti_bot_type": None,
                "bypass_method": "headless_browser",
                "loan_page_urls": ["https://bca.co.id/kpr"],
                "selectors": {},
                "rate_limit_ms": 2000,
            }
            result = await agent.run(bank_code="BCA")
        db.upsert_strategy.assert_called_once()
        assert result["strategies_created"] == 1

    @pytest.mark.asyncio
    async def test_run_skips_inactive_banks(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "INACTIVE",
                "website_url": "https://example.com",
                "api_available": False,
                "website_status": "down",
            }
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        agent = StrategistAgent(db=db)
        result = await agent.run()
        assert result["strategies_created"] == 0
        db.upsert_strategy.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_skips_banks_with_existing_strategy(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "BCA",
                "website_url": "https://bca.co.id",
                "api_available": False,
                "website_status": "active",
            }
        ])
        db.fetch_active_strategies = AsyncMock(
            return_value=[{"id": "existing", "bank_id": "uuid1"}]
        )
        agent = StrategistAgent(db=db)
        result = await agent.run(bank_code="BCA")
        assert result["strategies_created"] == 0

    @pytest.mark.asyncio
    async def test_run_force_overrides_existing_strategy(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "BCA",
                "website_url": "https://bca.co.id",
                "api_available": False,
                "website_status": "active",
            }
        ])
        db.fetch_active_strategies = AsyncMock(
            return_value=[{"id": "existing", "bank_id": "uuid1"}]
        )
        db.upsert_strategy = AsyncMock(
            return_value={"id": "strat2", "bank_id": "uuid1", "version": 2}
        )
        agent = StrategistAgent(db=db)
        with patch.object(
            agent, "_analyze_bank", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.return_value = {
                "anti_bot_detected": False,
                "anti_bot_type": None,
                "bypass_method": "headless_browser",
                "loan_page_urls": ["https://bca.co.id/kpr"],
                "selectors": {},
                "rate_limit_ms": 2000,
            }
            result = await agent.run(bank_code="BCA", force=True)
        assert result["strategies_updated"] >= 1

    @pytest.mark.asyncio
    async def test_run_handles_analyze_error(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "BCA",
                "website_url": "https://bca.co.id",
                "api_available": False,
                "website_status": "active",
            }
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        agent = StrategistAgent(db=db)
        with patch.object(
            agent, "_analyze_bank", new_callable=AsyncMock
        ) as mock_analyze:
            mock_analyze.side_effect = Exception("Connection timeout")
            result = await agent.run(bank_code="BCA")
        assert result["errors"] == 1
        assert result["strategies_created"] == 0

    @pytest.mark.asyncio
    async def test_run_stops_shared_browser_manager(self):
        """All-bank runs must clean up the shared Playwright manager."""
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {
                "id": "uuid1",
                "bank_code": "BCA",
                "website_url": "https://bca.co.id",
                "api_available": False,
                "website_status": "active",
            }
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.upsert_strategy = AsyncMock()

        mock_manager = AsyncMock()
        with patch("ceres.agents.strategist.BrowserManager", return_value=mock_manager):
            agent = StrategistAgent(db=db)
            with patch.object(
                agent, "_analyze_bank", new_callable=AsyncMock
            ) as mock_analyze:
                mock_analyze.return_value = {
                    "anti_bot_detected": False,
                    "anti_bot_type": None,
                    "bypass_method": "headless_browser",
                    "loan_page_urls": ["https://bca.co.id/kpr"],
                    "selectors": {},
                    "rate_limit_ms": 2000,
                }
                await agent.run()

        mock_manager.stop.assert_called_once()

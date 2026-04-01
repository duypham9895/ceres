"""Tests for LabAgent — strategy fix testing with approach escalation."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from ceres.agents.lab import LabAgent


class TestLabAgent:
    @pytest.mark.asyncio
    async def test_run_tests_approaches_sequentially(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(
            return_value=[
                {
                    "id": "strat1",
                    "bank_id": "uuid1",
                    "bank_code": "BCA",
                    "bank_name": "BCA",
                    "website_url": "https://bca.co.id",
                    "bypass_method": "headless_browser",
                    "loan_page_urls": '["https://bca.co.id/kpr"]',
                    "selectors": "{}",
                    "rate_limit_ms": 2000,
                    "anti_bot_detected": True,
                    "version": 1,
                    "success_rate": 0.0,
                },
            ]
        )
        db.add_strategy_feedback = AsyncMock(return_value="fb1")
        db.upsert_strategy = AsyncMock(
            return_value={"id": "strat1", "bank_id": "uuid1", "version": 2}
        )
        agent = LabAgent(db=db)
        with patch.object(
            agent, "_test_approach", new_callable=AsyncMock
        ) as mock_test:
            mock_test.side_effect = [
                {"success": False},
                {"success": True, "bypass_method": "undetected_chrome"},
            ]
            result = await agent.run(bank_code="BCA")
        assert result["tests_run"] >= 2
        assert result["fixes_found"] == 1

    @pytest.mark.asyncio
    async def test_escalates_after_max_attempts(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(
            return_value=[
                {
                    "id": "strat1",
                    "bank_id": "uuid1",
                    "bank_code": "BCA",
                    "bank_name": "BCA",
                    "website_url": "https://bca.co.id",
                    "bypass_method": "headless_browser",
                    "loan_page_urls": '["https://bca.co.id/kpr"]',
                    "selectors": "{}",
                    "rate_limit_ms": 2000,
                    "anti_bot_detected": True,
                    "version": 1,
                    "success_rate": 0.0,
                },
            ]
        )
        db.add_strategy_feedback = AsyncMock(return_value="fb1")
        agent = LabAgent(db=db)
        with patch.object(
            agent, "_test_approach", new_callable=AsyncMock
        ) as mock_test:
            mock_test.return_value = {"success": False}
            result = await agent.run(bank_code="BCA")
        assert result["escalated"] == 1

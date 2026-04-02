"""Tests for StrategistAgent force=True rebuild behavior."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ceres.agents.strategist import StrategistAgent


class TestStrategistForce:
    @pytest.mark.asyncio
    async def test_skips_existing_without_force(self):
        """Should skip banks with active strategies when force=False."""
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "uuid-1", "bank_code": "bca", "website_url": "https://bca.co.id", "website_status": "active"},
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[
            {"bank_id": "uuid-1", "bank_code": "bca"},
        ])

        agent = StrategistAgent(db=db)
        result = await agent.run(force=False)

        assert result["strategies_created"] == 0
        assert result["strategies_updated"] == 0

    @pytest.mark.asyncio
    async def test_rebuilds_existing_with_force(self):
        """Should rebuild existing strategies when force=True."""
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "uuid-1", "bank_code": "bca", "website_url": "https://bca.co.id",
             "website_status": "active", "api_available": False},
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[
            {"bank_id": "uuid-1", "bank_code": "bca"},
        ])
        db.upsert_strategy = AsyncMock(return_value={"id": "s-1"})

        agent = StrategistAgent(db=db)

        with patch.object(agent, "_analyze_bank", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "anti_bot_detected": False,
                "anti_bot_type": None,
                "bypass_method": "headless_browser",
                "loan_page_urls": ["https://bca.co.id/kpr"],
                "selectors": {},
                "rate_limit_ms": 2000,
            }
            result = await agent.run(force=True)

        assert result["strategies_updated"] == 1
        db.upsert_strategy.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_strategy_without_force(self):
        """Should create strategies for banks without existing ones, even without force."""
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "uuid-2", "bank_code": "bni", "website_url": "https://bni.co.id",
             "website_status": "active", "api_available": False},
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])  # No existing
        db.upsert_strategy = AsyncMock(return_value={"id": "s-2"})

        agent = StrategistAgent(db=db)

        with patch.object(agent, "_analyze_bank", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "anti_bot_detected": False,
                "anti_bot_type": None,
                "bypass_method": "headless_browser",
                "loan_page_urls": ["https://bni.co.id/kpr"],
                "selectors": {},
                "rate_limit_ms": 2000,
            }
            result = await agent.run(force=False)

        assert result["strategies_created"] == 1
        db.upsert_strategy.assert_called_once()

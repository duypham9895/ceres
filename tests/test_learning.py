"""Tests for the Learning agent."""

import pytest
from unittest.mock import AsyncMock

from ceres.agents.learning import LearningAgent


class TestLearningAgent:
    @pytest.mark.asyncio
    async def test_calculates_success_rates(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 100, "successes": 80, "failures": 15,
            "blocked": 5, "banks_crawled": 50, "total_programs_found": 200,
        })
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "is_partner_ringkas": False, "bank_name": "BCA"},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value="rec1")
        agent = LearningAgent(db=db)
        result = await agent.run()
        assert result["overall_success_rate"] == 0.8
        assert "report" in result

    @pytest.mark.asyncio
    async def test_identifies_partnership_opportunities(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successes": 8, "failures": 2,
            "blocked": 0, "banks_crawled": 5, "total_programs_found": 20,
        })
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "NEWBANK", "is_partner_ringkas": False, "bank_name": "New Bank"},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[
            {"bank_id": "1", "bank_code": "NEWBANK", "loan_type": "KPR",
             "program_name": "KPR NewBank", "min_interest_rate": 3.0,
             "completeness_score": 0.9, "data_confidence": 0.8},
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value="rec1")
        agent = LearningAgent(db=db)
        result = await agent.run()
        db.add_recommendation.assert_called()
        call_kwargs = db.add_recommendation.call_args.kwargs
        assert call_kwargs["rec_type"] == "partnership_opportunity"

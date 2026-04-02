"""Tests for the Learning agent."""

import pytest
from unittest.mock import AsyncMock

from ceres.agents.learning import LearningAgent


def _mock_rec_row(rec_id="rec1", rec_type="product_gap"):
    """Return a dict mimicking a RETURNING * row from ringkas_recommendations."""
    return {
        "id": rec_id,
        "rec_type": rec_type,
        "priority": 3,
        "title": "test",
        "summary": "test summary",
        "impact_score": 0.5,
        "suggested_actions": "[]",
        "status": "pending",
        "created_at": "2026-04-01T00:00:00Z",
        "updated_at": "2026-04-01T00:00:00Z",
    }


class TestLearningAgent:
    @pytest.mark.asyncio
    async def test_calculates_success_rates(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 100, "successful": 80, "failed": 15,
            "blocked": 5, "banks_crawled": 50, "total_programs_found": 200,
        })
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "is_partner_ringkas": False, "bank_name": "BCA"},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row())
        db.clear_recommendations_by_type = AsyncMock(return_value=0)
        agent = LearningAgent(db=db)
        result = await agent.run()
        assert result["overall_success_rate"] == 0.8
        assert "report" in result

    @pytest.mark.asyncio
    async def test_uses_correct_crawl_stats_keys(self):
        """Verify learning agent reads 'successful'/'failed' (not 'successes'/'failures')."""
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 50, "successful": 40, "failed": 8,
            "blocked": 2, "total_programs_found": 100,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row())
        db.clear_recommendations_by_type = AsyncMock(return_value=0)

        agent = LearningAgent(db=db)
        result = await agent.run()
        assert result["overall_success_rate"] == 0.8
        assert result["failures"] == 8

    @pytest.mark.asyncio
    async def test_generates_product_gap_recommendations(self):
        """Product gap recs are created with correct kwargs (priority, title, summary)."""
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successful": 8, "failed": 2,
            "blocked": 0, "total_programs_found": 5,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        # Only KPR covered, so KPA/KPT/MULTIGUNA/KENDARAAN/MODAL_KERJA are gaps
        db.fetch_loan_programs = AsyncMock(return_value=[
            {"bank_code": "BCA", "loan_type": "KPR"},
        ])
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row())
        db.clear_recommendations_by_type = AsyncMock(return_value=0)

        agent = LearningAgent(db=db)
        result = await agent.run()

        # Should have called add_recommendation for each missing type
        product_gap_calls = [
            c for c in db.add_recommendation.call_args_list
            if c.kwargs.get("rec_type") == "product_gap"
        ]
        assert len(product_gap_calls) == 5  # KENDARAAN, KPA, KPT, MODAL_KERJA, MULTIGUNA

        # Verify kwargs match the fixed signature
        first_call = product_gap_calls[0].kwargs
        assert "priority" in first_call
        assert "title" in first_call
        assert "summary" in first_call
        assert "impact_score" in first_call
        assert "bank_code" not in first_call
        assert "details" not in first_call

    @pytest.mark.asyncio
    async def test_identifies_partnership_opportunities(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successful": 8, "failed": 2,
            "blocked": 0, "total_programs_found": 20,
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
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row(rec_type="partnership_opportunity"))
        db.clear_recommendations_by_type = AsyncMock(return_value=0)
        agent = LearningAgent(db=db)
        result = await agent.run()

        partnership_calls = [
            c for c in db.add_recommendation.call_args_list
            if c.kwargs.get("rec_type") == "partnership_opportunity"
        ]
        assert len(partnership_calls) == 1
        call_kwargs = partnership_calls[0].kwargs
        assert call_kwargs["rec_type"] == "partnership_opportunity"
        assert "priority" in call_kwargs
        assert "title" in call_kwargs
        assert "summary" in call_kwargs
        assert call_kwargs["impact_score"] == 0.8
        assert "bank_code" not in call_kwargs

    @pytest.mark.asyncio
    async def test_clears_existing_recommendations_before_insert(self):
        """Verify dedup: existing recs are cleared before generating new ones."""
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successful": 8, "failed": 2,
            "blocked": 0, "total_programs_found": 5,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row())
        db.clear_recommendations_by_type = AsyncMock(return_value=3)

        agent = LearningAgent(db=db)
        await agent.run()

        clear_calls = db.clear_recommendations_by_type.call_args_list
        cleared_types = {c.kwargs["rec_type"] for c in clear_calls}
        assert "product_gap" in cleared_types
        assert "partnership_opportunity" in cleared_types

    @pytest.mark.asyncio
    async def test_no_product_gaps_when_all_types_covered(self):
        """When all loan types are present, no product gap recs should be created."""
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successful": 10, "failed": 0,
            "blocked": 0, "total_programs_found": 60,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[
            {"bank_code": "BCA", "loan_type": lt}
            for lt in ["KPR", "KPA", "KPT", "MULTIGUNA", "KENDARAAN", "MODAL_KERJA"]
        ])
        db.add_recommendation = AsyncMock(return_value=_mock_rec_row())
        db.clear_recommendations_by_type = AsyncMock(return_value=0)

        agent = LearningAgent(db=db)
        await agent.run()

        product_gap_calls = [
            c for c in db.add_recommendation.call_args_list
            if c.kwargs.get("rec_type") == "product_gap"
        ]
        assert len(product_gap_calls) == 0

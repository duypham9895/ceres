"""Tests for the Agent Stats Framework — pipeline health metrics.

Covers:
- Completeness score fix (tenure→tenor, phantom field removal)
- update_crawl_log_programs() targeted update
- mark_parsed() with programs_produced
- Parser programs_found accumulation and crawl_log update
- get_parse_stats() and get_bank_crawl_stats() queries
- /api/pipeline-health endpoint
- Learning agent parse success rate in report
"""

from __future__ import annotations

import json
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ceres.models import calculate_completeness_score, _COMPLETENESS_FIELDS


# ------------------------------------------------------------------
# Completeness score
# ------------------------------------------------------------------


class TestCompletenessFieldsFix:
    def test_fields_use_tenor_not_tenure(self):
        """Fields must match DB column names (min_tenor_months, not min_tenure_months)."""
        assert "min_tenor_months" in _COMPLETENESS_FIELDS
        assert "max_tenor_months" in _COMPLETENESS_FIELDS
        assert "min_tenure_months" not in _COMPLETENESS_FIELDS
        assert "max_tenure_months" not in _COMPLETENESS_FIELDS

    def test_phantom_fields_removed(self):
        """rate_type and min_dp_percentage should not be in completeness fields."""
        assert "rate_type" not in _COMPLETENESS_FIELDS
        assert "min_dp_percentage" not in _COMPLETENESS_FIELDS

    def test_exactly_eight_fields(self):
        assert len(_COMPLETENESS_FIELDS) == 8

    def test_score_with_all_db_fields(self):
        """A program dict using actual DB column names should score 1.0."""
        data = {
            "program_name": "KPR Test",
            "loan_type": "KPR",
            "min_interest_rate": 3.5,
            "max_interest_rate": 7.0,
            "min_amount": 100_000_000,
            "max_amount": 5_000_000_000,
            "min_tenor_months": 12,
            "max_tenor_months": 300,
        }
        assert calculate_completeness_score(data) == 1.0

    def test_score_with_old_field_names_does_not_count(self):
        """Old field names (tenure, rate_type) should NOT contribute to score."""
        data = {
            "program_name": "KPR Test",
            "loan_type": "KPR",
            "min_tenure_months": 12,
            "max_tenure_months": 300,
            "rate_type": "MIXED",
            "min_dp_percentage": 10,
        }
        assert calculate_completeness_score(data) == 0.25  # 2/8


# ------------------------------------------------------------------
# Parser stats accumulation
# ------------------------------------------------------------------


class TestParserStatsAccumulation:
    @pytest.mark.asyncio
    async def test_programs_by_log_accumulated(self):
        """Parser should accumulate programs_found per crawl_log_id."""
        from ceres.agents.parser import ParserAgent

        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[
            {
                "id": "raw1",
                "bank_id": "uuid1",
                "bank_code": "BCA",
                "bank_name": "Bank Central Asia",
                "page_url": "https://bca.co.id/kpr",
                # raw_html now fetched separately via fetch_raw_html_by_id
                "selectors": None,
                "crawl_log_id": "log1",
            },
            {
                "id": "raw2",
                "bank_id": "uuid1",
                "bank_code": "BCA",
                "bank_name": "Bank Central Asia",
                "page_url": "https://bca.co.id/kpa",
                # raw_html now fetched separately via fetch_raw_html_by_id
                "selectors": None,
                "crawl_log_id": "log1",
            },
        ])
        db.fetch_raw_html_by_id = AsyncMock(return_value="<div>text</div>")
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1"})
        db.mark_parsed = AsyncMock()
        db.update_crawl_log_programs = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(return_value={
            "programs": [{"program_name": "Test KPR", "loan_type": "KPR", "min_interest_rate": 5.5, "max_interest_rate": 8.0}]
        })

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        result = await agent.run()

        assert result["programs_parsed"] == 2
        db.update_crawl_log_programs.assert_called_once_with(
            crawl_log_id="log1", programs_found=2,
        )

    @pytest.mark.asyncio
    async def test_null_crawl_log_id_skipped(self):
        """When crawl_log_id is None (re-parse), skip crawl_log update."""
        from ceres.agents.parser import ParserAgent

        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[
            {
                "id": "raw1",
                "bank_id": "uuid1",
                "bank_code": "BCA",
                "bank_name": "Bank Central Asia",
                "page_url": "https://bca.co.id/kpr",
                # raw_html now fetched separately via fetch_raw_html_by_id
                "selectors": None,
                "crawl_log_id": None,
            },
        ])
        db.fetch_raw_html_by_id = AsyncMock(return_value="<div>text</div>")
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1"})
        db.mark_parsed = AsyncMock()
        db.update_crawl_log_programs = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(return_value={
            "programs": [{"program_name": "Test", "loan_type": "KPR", "min_interest_rate": 5.5}]
        })

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        await agent.run()

        db.update_crawl_log_programs.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_parsed_includes_programs_produced(self):
        """mark_parsed should be called with programs_produced count."""
        from ceres.agents.parser import ParserAgent

        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[
            {
                "id": "raw1",
                "bank_id": "uuid1",
                "bank_code": "BCA",
                "bank_name": "Bank Central Asia",
                "page_url": "https://bca.co.id/kpr",
                # raw_html now fetched separately via fetch_raw_html_by_id
                "selectors": None,
                "crawl_log_id": "log1",
            },
        ])
        db.fetch_raw_html_by_id = AsyncMock(return_value="<div>text</div>")
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1"})
        db.mark_parsed = AsyncMock()
        db.update_crawl_log_programs = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(return_value={
            "programs": [
                {"program_name": "KPR A", "loan_type": "KPR", "min_interest_rate": 5.5, "max_interest_rate": 8.0},
                {"program_name": "KPR B", "loan_type": "KPR", "min_interest_rate": 6.0, "max_interest_rate": 9.0},
            ]
        })

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        await agent.run()

        db.mark_parsed.assert_called_once_with(
            raw_data_id="raw1", programs_produced=2,
        )

    @pytest.mark.asyncio
    async def test_crawl_log_update_failure_does_not_fail_parse(self):
        """If update_crawl_log_programs fails, parse should still succeed."""
        from ceres.agents.parser import ParserAgent

        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[
            {
                "id": "raw1",
                "bank_id": "uuid1",
                "bank_code": "BCA",
                "bank_name": "Bank Central Asia",
                "page_url": "https://bca.co.id/kpr",
                # raw_html now fetched separately via fetch_raw_html_by_id
                "selectors": None,
                "crawl_log_id": "log1",
            },
        ])
        db.fetch_raw_html_by_id = AsyncMock(return_value="<div>text</div>")
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1"})
        db.mark_parsed = AsyncMock()
        db.update_crawl_log_programs = AsyncMock(
            side_effect=Exception("DB connection lost")
        )

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(return_value={
            "programs": [{"program_name": "Test", "loan_type": "KPR", "min_interest_rate": 5.5}]
        })

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        result = await agent.run()

        assert result["programs_parsed"] == 1
        assert len(result["errors"]) == 0


# ------------------------------------------------------------------
# Learning agent report
# ------------------------------------------------------------------


class TestLearningReportParseStats:
    @pytest.mark.asyncio
    async def test_report_includes_parse_success(self):
        """Learning report should include parse success rate."""
        from ceres.agents.learning import LearningAgent

        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10,
            "banks_crawled": 3,
            "successful": 8,
            "failed": 2,
            "blocked": 0,
            "timed_out": 0,
            "total_programs_found": 5,
            "total_programs_new": 0,
            "avg_duration_ms": 500,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.get_parse_stats = AsyncMock(return_value=[
            {
                "bank_code": "BCA",
                "total_raw_rows": 10,
                "parsed_rows": 8,
                "rows_with_programs": 6,
                "total_programs_produced": 12,
            },
        ])
        db.clear_recommendations_by_type = AsyncMock(return_value=0)

        agent = LearningAgent(db=db)
        result = await agent.run(days=7)

        assert "parse_success_rate" in result
        assert result["parse_success_rate"] == 0.6  # 6/10
        assert "Parse Success" in result["report"]
        assert "BCA: 6/10 (60%)" in result["report"]

    @pytest.mark.asyncio
    async def test_banks_crawled_from_stats(self):
        """Learning report should include banks_crawled from get_crawl_stats."""
        from ceres.agents.learning import LearningAgent

        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 5,
            "banks_crawled": 3,
            "successful": 5,
            "failed": 0,
            "blocked": 0,
            "timed_out": 0,
            "total_programs_found": 0,
            "total_programs_new": 0,
            "avg_duration_ms": 0,
        })
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.get_parse_stats = AsyncMock(return_value=[])
        db.clear_recommendations_by_type = AsyncMock(return_value=0)

        agent = LearningAgent(db=db)
        result = await agent.run(days=7)

        assert result["banks_crawled"] == 3
        assert "Banks Crawled:      3" in result["report"]


# ------------------------------------------------------------------
# Pipeline health endpoint
# ------------------------------------------------------------------


class TestPipelineHealthEndpoint:
    @pytest.mark.asyncio
    async def test_pipeline_health_response_shape(self):
        """The /pipeline-health endpoint should return crawl, parse, strategies sections."""
        from ceres.api.routes import pipeline_health

        mock_db = AsyncMock()
        mock_db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 20,
            "banks_crawled": 5,
            "successful": 16,
            "failed": 3,
            "blocked": 1,
            "timed_out": 0,
            "total_programs_found": 10,
            "total_programs_new": 0,
            "avg_duration_ms": 400,
        })
        mock_db.get_bank_crawl_stats = AsyncMock(return_value=[
            {"bank_code": "BCA", "total_crawls": 10, "successful": 8, "failed": 1, "blocked": 1},
            {"bank_code": "BRI", "total_crawls": 10, "successful": 8, "failed": 2, "blocked": 0},
        ])
        mock_db.get_parse_stats = AsyncMock(return_value=[
            {"bank_code": "BCA", "total_raw_rows": 8, "parsed_rows": 7, "rows_with_programs": 5, "total_programs_produced": 10},
            {"bank_code": "BRI", "total_raw_rows": 6, "parsed_rows": 5, "rows_with_programs": 4, "total_programs_produced": 8},
        ])
        mock_db.fetch_active_strategies = AsyncMock(return_value=[
            {"bank_code": "BCA", "success_rate": 0.85, "anti_bot_detected": False},
            {"bank_code": "BRI", "success_rate": 0.20, "anti_bot_detected": True},
        ])

        request = MagicMock()
        request.app.state.db = mock_db

        result = await pipeline_health(request, days=7)

        assert "crawl" in result
        assert "parse" in result
        assert "strategies" in result

        assert result["crawl"]["overall_success_rate"] == 0.8
        assert result["crawl"]["total_crawls"] == 20
        assert len(result["crawl"]["by_bank"]) == 2

        assert result["parse"]["total_raw_rows"] == 14
        assert len(result["parse"]["by_bank"]) == 2

        assert result["strategies"]["total_active"] == 2
        assert len(result["strategies"]["failing"]) == 1
        assert result["strategies"]["failing"][0]["bank_code"] == "BRI"

    @pytest.mark.asyncio
    async def test_pipeline_health_empty_data(self):
        """Pipeline health should handle zero data gracefully."""
        from ceres.api.routes import pipeline_health

        mock_db = AsyncMock()
        mock_db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 0, "banks_crawled": 0, "successful": 0,
            "failed": 0, "blocked": 0, "timed_out": 0,
            "total_programs_found": 0, "total_programs_new": 0,
            "avg_duration_ms": 0,
        })
        mock_db.get_bank_crawl_stats = AsyncMock(return_value=[])
        mock_db.get_parse_stats = AsyncMock(return_value=[])
        mock_db.fetch_active_strategies = AsyncMock(return_value=[])

        request = MagicMock()
        request.app.state.db = mock_db

        result = await pipeline_health(request, days=7)

        assert result["crawl"]["overall_success_rate"] == 0.0
        assert result["parse"]["overall_success_rate"] == 0.0
        assert result["strategies"]["total_active"] == 0
        assert result["strategies"]["failing"] == []

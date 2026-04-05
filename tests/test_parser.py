"""Tests for the Parser agent with selector extraction and LLM fallback."""

import json

import pytest
from unittest.mock import AsyncMock

from ceres.agents.parser import ParserAgent


_HTML_WITH_SELECTORS = (
    '<div class="product">'
    '<h3 class="name">KPR BCA</h3>'
    '<span class="rate">3.5% - 7.0%</span>'
    "</div>"
)

_HTML_UNSTRUCTURED = "<div>Some unstructured text about loans</div>"


def _make_row(raw_id="raw1", selectors=None, **overrides):
    """Build an unparsed row (metadata only, no raw_html)."""
    row = {
        "id": raw_id,
        "bank_id": "uuid1",
        "bank_code": "BCA",
        "bank_name": "Bank Central Asia",
        "page_url": "https://bca.co.id/kpr",
        "crawl_log_id": None,
        "selectors": json.dumps(selectors) if selectors else None,
        **overrides,
    }
    return row


class TestParserAgent:
    @pytest.mark.asyncio
    async def test_parse_with_selectors(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[
                _make_row(
                    selectors={
                        "container": "div.product",
                        "fields": {"name": "h3.name", "rate": "span.rate"},
                    },
                ),
            ]
        )
        db.fetch_raw_html_by_id = AsyncMock(return_value=_HTML_WITH_SELECTORS)
        db.upsert_loan_program = AsyncMock(
            return_value={
                "id": "lp1",
                "program_name": "KPR BCA",
                "loan_type": "KPR",
            }
        )
        db.mark_parsed = AsyncMock()

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] >= 1
        db.fetch_raw_html_by_id.assert_called_once_with(raw_data_id="raw1")
        db.mark_parsed.assert_called_once_with(
            raw_data_id="raw1", programs_produced=1,
        )

    @pytest.mark.asyncio
    async def test_llm_fallback_on_low_confidence(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[_make_row(selectors=None)]
        )
        db.fetch_raw_html_by_id = AsyncMock(return_value=_HTML_UNSTRUCTURED)
        db.upsert_loan_program = AsyncMock(
            return_value={
                "id": "lp1",
                "program_name": "KPR BCA",
                "loan_type": "KPR",
            }
        )
        db.mark_parsed = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(
            return_value={
                "programs": [
                    {
                        "program_name": "KPR BCA",
                        "loan_type": "KPR",
                        "min_interest_rate": 3.5,
                    }
                ]
            }
        )

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        result = await agent.run()

        mock_llm.extract_loan_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_unparsed_data(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[])

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] == 0

    @pytest.mark.asyncio
    async def test_skips_row_when_html_deleted(self):
        """If raw_html was deleted between metadata fetch and HTML fetch, skip it."""
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[_make_row()]
        )
        db.fetch_raw_html_by_id = AsyncMock(return_value=None)

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] == 0

    @pytest.mark.asyncio
    async def test_heuristic_fallback_extracts_program_without_selectors_or_llm(self):
        """Parser should still extract baseline data from obvious loan content."""
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[_make_row(selectors=None)]
        )
        db.fetch_raw_html_by_id = AsyncMock(
            return_value=(
                '<section class="product">'
                '<h2>KPR BCA</h2>'
                '<p>Bunga 3,5% s.d. 7,0%</p>'
                '<p>Plafon Rp 500 Juta - 2 Miliar</p>'
                '<p>Tenor hingga 20 tahun</p>'
                '</section>'
            )
        )
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1"})
        db.mark_parsed = AsyncMock()

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] == 1
        upsert_kwargs = db.upsert_loan_program.call_args.kwargs
        assert upsert_kwargs["program_name"] == "KPR BCA"
        assert upsert_kwargs["loan_type"] == "KPR"
        assert upsert_kwargs["min_interest_rate"] == 3.5
        assert upsert_kwargs["max_interest_rate"] == 7.0
        assert upsert_kwargs["min_amount"] == 500_000_000
        assert upsert_kwargs["max_amount"] == 2_000_000_000
        assert upsert_kwargs["max_tenor_months"] == 240

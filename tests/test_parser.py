"""Tests for the Parser agent with selector extraction and LLM fallback."""

import json

import pytest
from unittest.mock import AsyncMock

from ceres.agents.parser import ParserAgent


class TestParserAgent:
    @pytest.mark.asyncio
    async def test_parse_with_selectors(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[
                {
                    "id": "raw1",
                    "bank_id": "uuid1",
                    "bank_code": "BCA",
                    "bank_name": "Bank Central Asia",
                    "page_url": "https://bca.co.id/kpr",
                    "raw_html": (
                        '<div class="product">'
                        '<h3 class="name">KPR BCA</h3>'
                        '<span class="rate">3.5% - 7.0%</span>'
                        "</div>"
                    ),
                    "selectors": json.dumps(
                        {
                            "container": "div.product",
                            "fields": {"name": "h3.name", "rate": "span.rate"},
                        }
                    ),
                }
            ]
        )
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
        db.mark_parsed.assert_called_once_with("raw1")

    @pytest.mark.asyncio
    async def test_llm_fallback_on_low_confidence(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(
            return_value=[
                {
                    "id": "raw1",
                    "bank_id": "uuid1",
                    "bank_code": "BCA",
                    "bank_name": "Bank Central Asia",
                    "page_url": "https://bca.co.id/kpr",
                    "raw_html": "<div>Some unstructured text about loans</div>",
                    "selectors": None,
                }
            ]
        )
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

"""Parser agent: extracts loan programs from crawled HTML pages.

Uses CSS selector-based extraction as primary strategy, with LLM-based
extraction as fallback when selectors are missing or produce low-confidence
results.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.database import Database
from ceres.extractors.llm import LLMExtractor
from ceres.extractors.normalizer import (
    normalize_amount,
    normalize_loan_type,
    normalize_rate,
    normalize_tenure,
)
from ceres.extractors.selector import SelectorExtractor
from ceres.models import calculate_completeness_score

LLM_CONFIDENCE_THRESHOLD = 0.5

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """Agent that parses crawled HTML into structured loan program data."""

    name: str = "parser"

    def __init__(
        self,
        db: Database,
        config: Optional[Any] = None,
        llm_extractor: Optional[LLMExtractor] = None,
    ) -> None:
        super().__init__(db=db, config=config)
        self._selector_extractor = SelectorExtractor()
        self._llm_extractor = llm_extractor

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        """Parse unparsed HTML rows into loan programs.

        Args:
            bank_code: Optional filter to parse only a specific bank.

        Returns:
            Stats dict with programs_parsed count and any errors.
        """
        rows = await self.db.fetch_unparsed_html(bank_code=bank_code)
        self.logger.info(f"Found {len(rows)} unparsed rows, llm_extractor={self._llm_extractor is not None}")
        programs_parsed = 0
        errors: list[str] = []

        for raw in rows:
            try:
                programs = await self._parse_page(raw)
                self.logger.info(f"{raw.get('bank_code', '?')}: {len(programs)} programs from {raw.get('page_url', '?')[:60]}")
                for program in programs:
                    await self.db.upsert_loan_program(**program)
                    programs_parsed += 1
                await self.db.mark_parsed(raw_data_id=str(raw["id"]))
            except Exception as exc:
                error_msg = f"Failed to parse raw_id={raw['id']}: {exc}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        self.logger.info(f"Done: {programs_parsed} programs, {len(errors)} errors")
        return {"programs_parsed": programs_parsed, "errors": errors}

    async def _parse_page(self, raw: dict) -> list[dict]:
        """Extract loan programs from a single raw HTML row.

        Tries selector-based extraction first. Falls back to LLM extraction
        when selectors are absent or produce low-confidence results.

        Args:
            raw: Dict with id, bank_id, bank_code, bank_name, page_url,
                 raw_html, and selectors fields.

        Returns:
            List of program dicts ready for db.upsert_loan_program.
        """
        selectors = _parse_selectors(raw.get("selectors"))
        programs: list[dict] = []

        if selectors and selectors.get("fields"):
            results = self._selector_extractor.extract(
                raw["raw_html"], selectors
            )
            for result in results:
                if result.confidence >= LLM_CONFIDENCE_THRESHOLD:
                    program = self._normalize_fields(
                        result.fields, raw, result.confidence
                    )
                    if program is not None:
                        programs.append(program)

        if not programs and self._llm_extractor is not None:
            logger.info(
                "LLM fallback for %s (%s)",
                raw.get("bank_code", "?"),
                raw.get("page_url", "?"),
            )
            llm_data = await self._llm_extractor.extract_loan_data(
                raw["raw_html"], raw.get("bank_name", "Unknown Bank")
            )
            for prog_data in llm_data.get("programs", []):
                program = self._build_program_from_llm(prog_data, raw)
                if program is not None:
                    programs.append(program)

        return programs

    def _normalize_fields(
        self,
        fields: dict[str, str | None],
        raw: dict,
        confidence_base: float,
    ) -> dict | None:
        """Normalize extracted selector fields into a program dict.

        Args:
            fields: Raw field values from selector extraction.
            raw: The original raw HTML row for bank metadata.
            confidence_base: Confidence score from selector extraction.

        Returns:
            Program dict for upsert, or None if name field is missing.
        """
        name = fields.get("name")
        if not name:
            return None

        loan_type = normalize_loan_type(name)

        min_rate, max_rate = normalize_rate(fields.get("rate", "") or "")
        min_amount, max_amount = normalize_amount(fields.get("amount", "") or "")
        min_tenure, max_tenure = normalize_tenure(fields.get("tenure", "") or "")

        program = {
            "bank_id": str(raw["bank_id"]),
            "program_name": name,
            "loan_type": loan_type,
            "source_url": raw["page_url"],
            "min_interest_rate": min_rate,
            "max_interest_rate": max_rate,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "min_tenor_months": min_tenure,
            "max_tenor_months": max_tenure,
            "data_confidence": confidence_base,
        }

        program["completeness_score"] = calculate_completeness_score(program)
        return program

    def _build_program_from_llm(
        self, prog_data: dict, raw: dict
    ) -> dict | None:
        """Build a program dict from LLM-extracted data.

        Args:
            prog_data: Single program dict from LLM extraction response.
            raw: The original raw HTML row for bank metadata.

        Returns:
            Program dict for upsert, or None if program_name is missing.
        """
        program_name = prog_data.get("program_name")
        if not program_name:
            return None

        program = {
            "bank_id": str(raw["bank_id"]),
            "program_name": program_name,
            "loan_type": prog_data.get("loan_type", "OTHER"),
            "source_url": raw["page_url"],
            "min_interest_rate": prog_data.get("min_interest_rate"),
            "max_interest_rate": prog_data.get("max_interest_rate"),
            "min_amount": prog_data.get("min_amount"),
            "max_amount": prog_data.get("max_amount"),
            "min_tenor_months": prog_data.get("min_tenor_months"),
            "max_tenor_months": prog_data.get("max_tenor_months"),
            "data_confidence": 0.7,
        }

        program["completeness_score"] = calculate_completeness_score(program)
        return program


def _parse_selectors(selectors_raw: str | None) -> dict | None:
    """Parse a JSON selectors string into a dict.

    Returns None if input is None, empty, or invalid JSON.
    """
    if not selectors_raw:
        return None
    try:
        return json.loads(selectors_raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _run_sync(coro):
    """Await a coroutine from synchronous context using the running loop.

    This is used because _parse_page is synchronous but may need to call
    the async LLM extractor.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    if loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return loop.run_until_complete(coro)

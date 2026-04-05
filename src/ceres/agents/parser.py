"""Parser agent: extracts loan programs from crawled HTML pages.

Uses CSS selector-based extraction as primary strategy, with LLM-based
extraction as fallback when selectors are missing or produce low-confidence
results.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from lxml import html

from ceres.agents.base import BaseAgent
from ceres.database import Database
from ceres.extractors.llm import ClaudeLLMExtractor, LLMExtractor, MiniMaxLLMExtractor
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

_PROGRAM_KEYWORDS = re.compile(
    r"\b(kpr|kpa|kpt|kkb|multiguna|kendaraan|kredit|pinjaman|mortgage|refinancing|take over)\b",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")
_FALLBACK_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bKPR(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
    re.compile(r"\bKPA(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
    re.compile(r"\bKPT(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
    re.compile(r"\bKKB(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
    re.compile(r"\bKredit\s+Multiguna(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
    re.compile(r"\bPinjaman(?:\s+[A-Z0-9][A-Za-z0-9&()/.-]*)?", re.IGNORECASE),
)


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
        self._llm_extractor = llm_extractor or _auto_create_llm_extractor()

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        """Parse unparsed HTML rows into loan programs.

        Fetches row metadata first (no HTML), then loads HTML one row at a
        time to avoid holding hundreds of MB in memory simultaneously.

        Args:
            bank_code: Optional filter to parse only a specific bank.

        Returns:
            Stats dict with programs_parsed count and any errors.
        """
        rows = await self.db.fetch_unparsed_html(bank_code=bank_code)
        self.logger.info(f"Found {len(rows)} unparsed rows, llm_extractor={self._llm_extractor is not None}")
        programs_parsed = 0
        errors: list[str] = []
        programs_by_log: dict[str, int] = {}

        for raw in rows:
            try:
                # Load HTML one at a time to cap memory usage
                html = await self.db.fetch_raw_html_by_id(
                    raw_data_id=str(raw["id"]),
                )
                if html is None:
                    self.logger.warning(f"Raw data {raw['id']} disappeared, skipping")
                    continue

                # Build a view with html for _parse_page, then drop the reference
                raw_with_html = {**raw, "raw_html": html}
                programs = await self._parse_page(raw_with_html)
                del raw_with_html  # release HTML memory immediately

                self.logger.info(f"{raw.get('bank_code', '?')}: {len(programs)} programs from {raw.get('page_url', '?')[:60]}")
                for program in programs:
                    await self.db.upsert_loan_program(**program)
                    programs_parsed += 1
                await self.db.mark_parsed(
                    raw_data_id=str(raw["id"]),
                    programs_produced=len(programs),
                )

                crawl_log_id = raw.get("crawl_log_id")
                if crawl_log_id is not None:
                    log_key = str(crawl_log_id)
                    programs_by_log[log_key] = (
                        programs_by_log.get(log_key, 0) + len(programs)
                    )
            except Exception as exc:
                error_msg = f"Failed to parse raw_id={raw['id']}: {exc}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        for log_id, count in programs_by_log.items():
            try:
                await self.db.update_crawl_log_programs(
                    crawl_log_id=log_id, programs_found=count,
                )
            except Exception:
                self.logger.exception(
                    "Failed to update programs_found for crawl_log %s", log_id,
                )

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

        if not programs:
            programs = self._extract_programs_heuristically(raw)

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

    def _extract_programs_heuristically(self, raw: dict) -> list[dict]:
        """Best-effort extraction when selectors are absent and LLM is unavailable."""
        html_content = raw.get("raw_html", "")
        if not html_content.strip():
            return []

        try:
            tree = html.fromstring(html_content)
        except Exception:
            return []

        programs: list[dict] = []
        seen_names: set[str] = set()

        for element in tree.cssselect("h1, h2, h3, h4, h5, a, button, strong, b"):
            name = _normalize_text(element.text_content())
            if not _is_program_name(name):
                continue

            context_text = _extract_context_text(element)
            program = self._build_program_from_text(
                program_name=name,
                context_text=context_text,
                raw=raw,
                confidence=0.35,
            )
            if program is None:
                continue

            dedupe_key = program["program_name"].casefold()
            if dedupe_key in seen_names:
                continue
            seen_names.add(dedupe_key)
            programs.append(program)

        if programs:
            return programs

        full_text = _normalize_text(tree.text_content())
        for pattern in _FALLBACK_NAME_PATTERNS:
            for match in pattern.finditer(full_text):
                name = _normalize_text(match.group(0))
                if not _is_program_name(name):
                    continue
                dedupe_key = name.casefold()
                if dedupe_key in seen_names:
                    continue
                program = self._build_program_from_text(
                    program_name=name,
                    context_text=full_text,
                    raw=raw,
                    confidence=0.25,
                )
                if program is None:
                    continue
                seen_names.add(dedupe_key)
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

    def _build_program_from_text(
        self,
        *,
        program_name: str,
        context_text: str,
        raw: dict,
        confidence: float,
    ) -> dict | None:
        if not program_name:
            return None

        min_rate, max_rate = normalize_rate(context_text)
        min_amount, max_amount = normalize_amount(context_text)
        min_tenure, max_tenure = normalize_tenure(context_text)

        program = {
            "bank_id": str(raw["bank_id"]),
            "program_name": program_name,
            "loan_type": normalize_loan_type(program_name),
            "source_url": raw["page_url"],
            "min_interest_rate": min_rate,
            "max_interest_rate": max_rate,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "min_tenor_months": min_tenure,
            "max_tenor_months": max_tenure,
            "data_confidence": confidence,
            "raw_data": {"extraction_method": "heuristic"},
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
            "data_confidence": _calc_llm_confidence(prog_data),
        }

        program["completeness_score"] = calculate_completeness_score(program)
        return program


def _calc_llm_confidence(prog_data: dict) -> float:
    """Calculate confidence based on how many fields the LLM actually returned."""
    _LLM_FIELDS = (
        "program_name", "min_interest_rate", "max_interest_rate",
        "min_amount", "max_amount", "min_tenor_months", "max_tenor_months",
        "loan_type",
    )
    fields_present = sum(
        1 for f in _LLM_FIELDS if prog_data.get(f) is not None
    )
    return round(0.4 + (fields_present / 8) * 0.5, 2)


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


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _is_program_name(text: str) -> bool:
    return bool(
        text
        and len(text) <= 300
        and _PROGRAM_KEYWORDS.search(text)
    )


def _extract_context_text(element: html.HtmlElement) -> str:
    """Use a nearby section/article/div as extraction context when possible."""
    current = element
    for _ in range(8):
        parent = current.getparent()
        if parent is None:
            break
        current = parent
        text = _normalize_text(current.text_content())
        if 20 <= len(text) <= 5000:
            return text
    return _normalize_text(element.text_content())


def _auto_create_llm_extractor() -> LLMExtractor | None:
    """Auto-create an LLM extractor from available API keys."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=api_key)
            logger.info("Auto-creating ClaudeLLMExtractor from ANTHROPIC_API_KEY")
            return ClaudeLLMExtractor(client=client)
        except ImportError:
            logger.warning("anthropic package not installed; skipping Claude extractor")

    api_key = os.environ.get("MINIMAX_API_KEY")
    if api_key:
        logger.info("Auto-creating MiniMaxLLMExtractor from MINIMAX_API_KEY")
        return MiniMaxLLMExtractor(api_key=api_key)

    logger.warning("No LLM API key found; LLM extraction fallback disabled")
    return None



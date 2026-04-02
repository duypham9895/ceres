"""LLM-based extractor for loan data using Claude API as fallback."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_HTML_LENGTH = 50_000
MAX_CLEAN_TEXT_LENGTH = 20_000


def _strip_html_to_text(html: str) -> str:
    """Strip HTML tags, scripts, and styles to extract readable text.

    Raw HTML from bank websites is 50-300KB with JS bundles, CSS, and
    navigation. The LLM needs clean text content, not markup.
    """
    # Remove script and style blocks with their content
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&quot;", '"')
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

EXTRACTION_PROMPT = """\
You are an expert at extracting structured loan program data from bank websites.

Given the following HTML content from {bank_name}'s website, extract all loan programs \
and return a JSON object with this exact structure:

{{
  "programs": [
    {{
      "program_name": "string",
      "loan_type": "string (e.g. KPR, KPA, KKB, Multiguna)",
      "min_interest_rate": number_or_null,
      "max_interest_rate": number_or_null,
      "min_tenor_months": number_or_null,
      "max_tenor_months": number_or_null,
      "min_amount": number_or_null,
      "max_amount": number_or_null,
      "fixed_rate_period_months": number_or_null,
      "notes": "string_or_null"
    }}
  ]
}}

Return ONLY the JSON object, no other text. If no programs are found, return {{"programs": []}}.

HTML content:
{html}
"""


class LLMExtractor(ABC):
    """Abstract base class for LLM-based loan data extractors."""

    @abstractmethod
    async def extract_loan_data(self, html: str, bank_name: str) -> dict[str, Any]:
        """Extract loan program data from HTML using an LLM.

        Args:
            html: Raw HTML content from a bank website.
            bank_name: Name of the bank for context.

        Returns:
            Dictionary with 'programs' key containing extracted loan data,
            or an error dict if extraction fails.
        """


class ClaudeLLMExtractor(LLMExtractor):
    """Extracts loan data from HTML using the Claude API."""

    def __init__(self, client: Any, model: str = DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    async def extract_loan_data(self, html: str, bank_name: str) -> dict[str, Any]:
        """Extract loan program data from HTML via Claude API.

        Truncates HTML to MAX_HTML_LENGTH characters to stay within token limits.
        Handles JSON parse errors gracefully by attempting to find JSON in the
        response text before returning an error dict.
        """
        clean_text = _strip_html_to_text(html)[:MAX_CLEAN_TEXT_LENGTH]
        prompt = EXTRACTION_PROMPT.format(bank_name=bank_name, html=clean_text)

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text
            return _parse_json_response(raw_text)
        except Exception:
            return {"programs": [], "error": "Failed to parse LLM response"}


class MiniMaxLLMExtractor(LLMExtractor):
    """Extracts loan data from HTML using MiniMax API (OpenAI-compatible)."""

    MINIMAX_BASE_URL = "https://api.minimaxi.chat/v1"
    DEFAULT_MODEL = "MiniMax-M1"

    def __init__(
        self, api_key: str, model: str | None = None, base_url: str | None = None
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or self.MINIMAX_BASE_URL,
        )
        self._model = model or self.DEFAULT_MODEL

    async def extract_loan_data(self, html: str, bank_name: str) -> dict[str, Any]:
        """Extract loan program data from HTML via MiniMax API."""
        clean_text = _strip_html_to_text(html)[:MAX_CLEAN_TEXT_LENGTH]
        prompt = EXTRACTION_PROMPT.format(bank_name=bank_name, html=clean_text)

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.choices[0].message.content or ""
            return _parse_json_response(raw_text)
        except Exception as exc:
            print(f"[minimax] API error: {type(exc).__name__}: {exc}", flush=True)
            return {"programs": [], "error": f"MiniMax API: {exc}"}


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from LLM response text.

    Attempts direct parsing first, then searches for a JSON object
    within the text. Returns an error dict if no valid JSON is found.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"programs": [], "error": "Failed to parse LLM response"}

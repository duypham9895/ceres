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
You are an expert at extracting structured loan program data from Indonesian bank websites.

Given the following text content from {bank_name}'s website, extract ONLY real consumer \
loan products that a customer can apply for. Each program must have a clear product name \
and ideally include interest rates, loan amounts, or tenor information.

INCLUDE: KPR (mortgage), KPA (apartment), KPT (land), KKB/kredit kendaraan (vehicle), \
multiguna (multipurpose), kredit modal kerja (working capital), kredit investasi, \
kredit pendidikan, refinancing, take over.

EXCLUDE: Navigation menu items, page titles, "Simulasi Kredit" tools, "Suku Bunga Dasar" \
(base rate tables), internal/corporate credit facilities (kredit sindikasi, kredit BLUD, \
kredit BPR), and general category headings that are not actual products.

Return a JSON object with this exact structure:

{{
  "programs": [
    {{
      "program_name": "string — the actual product name (e.g. 'KPR BRI', 'Mandiri KPR Flexible')",
      "loan_type": "string — one of: KPR, KPA, KPT, MULTIGUNA, KENDARAAN, MODAL_KERJA, INVESTASI, PENDIDIKAN, PMI, TAKE_OVER, REFINANCING, OTHER",
      "min_interest_rate": "number or null — annual percentage (e.g. 3.5 means 3.5%)",
      "max_interest_rate": "number or null",
      "min_tenor_months": "number or null — in months",
      "max_tenor_months": "number or null — in months (e.g. 20 years = 240)",
      "min_amount": "number or null — in Rupiah (e.g. 100000000 for 100 juta)",
      "max_amount": "number or null — in Rupiah",
      "fixed_rate_period_months": "number or null — how long the fixed rate lasts",
      "notes": "string or null — any special conditions, promo details"
    }}
  ]
}}

Return ONLY the JSON object, no other text. If no real loan products are found, return {{"programs": []}}.

Text content:
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

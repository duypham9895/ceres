"""CSS selector-based HTML content extractor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lxml import html
from lxml.cssselect import CSSSelector


@dataclass(frozen=True)
class ExtractionResult:
    """Immutable result of extracting fields from a single container element."""

    fields: dict[str, str | None]
    confidence: float


class SelectorExtractor:
    """Extract structured data from HTML using CSS selectors.

    Expects a selector config dict with:
        - "container": CSS selector for repeating container elements
        - "fields": dict mapping field names to CSS selectors (relative to container)
    """

    def extract(
        self, html_content: str, selectors: dict[str, Any]
    ) -> list[ExtractionResult]:
        """Extract data from HTML using the provided CSS selectors.

        Args:
            html_content: Raw HTML string to parse.
            selectors: Dict with "container" and "fields" keys.

        Returns:
            List of ExtractionResult, one per matched container.
        """
        if not html_content or not html_content.strip():
            return []

        container_selector = selectors.get("container", "")
        field_selectors = selectors.get("fields", {})

        if not container_selector or not field_selectors:
            return []

        tree = html.fromstring(html_content)
        containers = CSSSelector(container_selector)(tree)

        if not containers:
            return []

        results: list[ExtractionResult] = []
        total_fields = len(field_selectors)

        for container in containers:
            extracted_fields = _extract_fields(container, field_selectors)
            fields_found = sum(
                1 for value in extracted_fields.values() if value is not None
            )
            confidence = fields_found / total_fields if total_fields > 0 else 0.0
            results.append(
                ExtractionResult(fields=extracted_fields, confidence=confidence)
            )

        return results


def _extract_fields(
    container: html.HtmlElement, field_selectors: dict[str, str]
) -> dict[str, str | None]:
    """Extract field values from a container element.

    Args:
        container: The parent HTML element to search within.
        field_selectors: Mapping of field name to CSS selector.

    Returns:
        Dict mapping field names to extracted text (or None if not found).
    """
    fields: dict[str, str | None] = {}

    for field_name, css_selector in field_selectors.items():
        matches = CSSSelector(css_selector)(container)
        if matches:
            text = matches[0].text_content().strip()
            fields[field_name] = text if text else None
        else:
            fields[field_name] = None

    return fields

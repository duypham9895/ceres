"""Normalizers for Indonesian banking product data.

Handles Indonesian-specific formats: comma decimals, "Juta"/"Miliar" suffixes,
"s.d." ranges, "tahun"/"bulan" time units, and banking product type keywords.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Rate normalization
# ---------------------------------------------------------------------------

_RATE_PATTERN = re.compile(r"(\d+[.,]\d+|\d+)\s*%")
_RANGE_SEPARATORS = re.compile(r"\s*(?:-|s\.?d\.?|sampai)\s*", re.IGNORECASE)


def normalize_rate(text: str) -> tuple[float | None, float | None]:
    """Parse interest rate text into (min_rate, max_rate).

    Handles formats:
        - "3.5% - 7.0%"
        - "5.25%"
        - "Bunga 3,5% s.d. 7,0%"  (Indonesian comma decimal + range)
        - "6.5% p.a."

    Returns (None, None) if no valid rate is found.
    """
    matches = _RATE_PATTERN.findall(text)
    if not matches:
        return (None, None)

    rates = [float(m.replace(",", ".")) for m in matches]

    if len(rates) == 1:
        return (rates[0], rates[0])
    return (min(rates), max(rates))


# ---------------------------------------------------------------------------
# Amount normalization
# ---------------------------------------------------------------------------

_JUTA_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*juta", re.IGNORECASE
)
_MILIAR_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*miliar", re.IGNORECASE
)
_DOT_NUMBER_PATTERN = re.compile(
    r"(\d{1,3}(?:\.\d{3})+)"
)


def normalize_amount(text: str) -> tuple[int | None, int | None]:
    """Parse loan amount text into (min_amount, max_amount) in Rupiah.

    Handles formats:
        - "Rp 500 Juta - 5 Miliar"
        - "100.000.000 - 5.000.000.000"  (dot-separated thousands)
        - "Rp 1 Miliar"
        - "1.5 Miliar"  (decimal with Juta/Miliar)

    Returns (None, None) if no valid amount is found.
    """
    amounts = _extract_named_amounts(text)

    if not amounts:
        amounts = _extract_dot_separated_amounts(text)

    if not amounts:
        return (None, None)

    if len(amounts) == 1:
        return (amounts[0], amounts[0])
    return (min(amounts), max(amounts))


def _parse_named_value(raw: str) -> float:
    """Convert a raw number string (possibly with comma decimal) to float."""
    return float(raw.replace(",", "."))


def _extract_named_amounts(text: str) -> list[int]:
    """Extract amounts using Juta/Miliar suffixes."""
    amounts: list[int] = []

    for match in _JUTA_PATTERN.finditer(text):
        value = _parse_named_value(match.group(1))
        amounts.append(int(value * 1_000_000))

    for match in _MILIAR_PATTERN.finditer(text):
        value = _parse_named_value(match.group(1))
        amounts.append(int(value * 1_000_000_000))

    return amounts


def _extract_dot_separated_amounts(text: str) -> list[int]:
    """Extract amounts from dot-separated thousand format (e.g., 100.000.000)."""
    amounts: list[int] = []

    for match in _DOT_NUMBER_PATTERN.finditer(text):
        raw = match.group(1).replace(".", "")
        amounts.append(int(raw))

    return amounts


# ---------------------------------------------------------------------------
# Loan type normalization
# ---------------------------------------------------------------------------

_LOAN_TYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"KPR|Kredit\s+Pemilikan\s+Rumah", re.IGNORECASE), "KPR"),
    (re.compile(r"KPA|Kredit\s+Pemilikan\s+Apartemen", re.IGNORECASE), "KPA"),
    (re.compile(r"KPT|Kredit\s+Pemilikan\s+Tanah", re.IGNORECASE), "KPT"),
    (re.compile(r"Multiguna", re.IGNORECASE), "MULTIGUNA"),
    (
        re.compile(r"Kendaraan|KKB|Kredit\s+Kendaraan\s+Bermotor", re.IGNORECASE),
        "KENDARAAN",
    ),
    (
        re.compile(r"Kredit\s+Modal\s+Kerja|KMK|Modal\s+Kerja", re.IGNORECASE),
        "MODAL_KERJA",
    ),
    (
        re.compile(r"Kredit\s+Investasi|KI\b|Investasi", re.IGNORECASE),
        "INVESTASI",
    ),
    (
        re.compile(r"Kredit\s+Pendidikan|Pinjaman\s+Pendidikan|Dana\s+Pendidikan", re.IGNORECASE),
        "PENDIDIKAN",
    ),
    (
        re.compile(r"Pekerja\s+Migran|PMI\b|TKI\b", re.IGNORECASE),
        "PMI",
    ),
    (
        re.compile(r"Take\s*Over|Takeover|Alih\s+Kredit", re.IGNORECASE),
        "TAKE_OVER",
    ),
    (
        re.compile(r"Refinancing|Refinansi|Top\s*Up", re.IGNORECASE),
        "REFINANCING",
    ),
]


def normalize_loan_type(text: str) -> str:
    """Classify loan product text into a standard loan type.

    Returns one of the LoanType enum values, or OTHER if no pattern matches.
    """
    for pattern, loan_type in _LOAN_TYPE_PATTERNS:
        if pattern.search(text):
            return loan_type
    return "OTHER"


# ---------------------------------------------------------------------------
# Tenure normalization
# ---------------------------------------------------------------------------

_TAHUN_PATTERN = re.compile(r"(\d+)\s*tahun", re.IGNORECASE)
_BULAN_PATTERN = re.compile(r"(\d+)\s*bulan", re.IGNORECASE)
_MAKS_PATTERN = re.compile(r"maks\.?\s*(\d+)\s*(tahun|bulan)", re.IGNORECASE)
_RANGE_NUMS = re.compile(r"(\d+)\s*(?:-|s\.?d\.?|sampai)\s*(\d+)")


def normalize_tenure(text: str) -> tuple[int | None, int | None]:
    """Parse tenure text into (min_months, max_months).

    Handles formats:
        - "1 - 25 tahun"  -> (12, 300)
        - "12 - 360 bulan" -> (12, 360)
        - "Maks. 20 tahun" -> (None, 240)

    Returns (None, None) if no valid tenure is found.
    """
    # Check for "Maks." prefix pattern first
    maks_match = _MAKS_PATTERN.search(text)
    if maks_match:
        value = int(maks_match.group(1))
        unit = maks_match.group(2).lower()
        months = value * 12 if unit == "tahun" else value
        return (None, months)

    # Check for range pattern
    range_match = _RANGE_NUMS.search(text)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        multiplier = _detect_multiplier(text)
        return (low * multiplier, high * multiplier)

    # Single value
    tahun_matches = _TAHUN_PATTERN.findall(text)
    if tahun_matches:
        value = int(tahun_matches[0])
        return (value * 12, value * 12)

    bulan_matches = _BULAN_PATTERN.findall(text)
    if bulan_matches:
        value = int(bulan_matches[0])
        return (value, value)

    return (None, None)


def _detect_multiplier(text: str) -> int:
    """Detect whether text refers to years (tahun) or months (bulan)."""
    text_lower = text.lower()
    if "tahun" in text_lower:
        return 12
    if "bulan" in text_lower:
        return 1
    return 1

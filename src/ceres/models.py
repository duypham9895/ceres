from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BankCategory(str, Enum):
    BUMN = "BUMN"
    SWASTA_NASIONAL = "SWASTA_NASIONAL"
    BPD = "BPD"
    ASING = "ASING"
    SYARIAH = "SYARIAH"


class BankType(str, Enum):
    KONVENSIONAL = "KONVENSIONAL"
    SYARIAH = "SYARIAH"


class LoanType(str, Enum):
    KPR = "KPR"
    KPA = "KPA"
    KPT = "KPT"
    MULTIGUNA = "MULTIGUNA"
    KENDARAAN = "KENDARAAN"
    MODAL_KERJA = "MODAL_KERJA"
    INVESTASI = "INVESTASI"
    PENDIDIKAN = "PENDIDIKAN"
    PMI = "PMI"
    TAKE_OVER = "TAKE_OVER"
    REFINANCING = "REFINANCING"
    OTHER = "OTHER"


class CrawlStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"


class WebsiteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNREACHABLE = "UNREACHABLE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class BypassMethod(str, Enum):
    HEADLESS_BROWSER = "HEADLESS_BROWSER"
    API = "API"
    PROXY_POOL = "PROXY_POOL"
    UNDETECTED_CHROME = "UNDETECTED_CHROME"
    MANUAL = "MANUAL"


# ---------------------------------------------------------------------------
# Frozen Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Bank:
    bank_code: str
    bank_name: str
    website_url: str
    bank_category: BankCategory
    bank_type: BankType
    id: Optional[int] = None
    is_partner_ringkas: bool = False
    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN


@dataclass(frozen=True)
class Strategy:
    bank_id: int
    id: Optional[int] = None
    selectors: dict = field(default_factory=dict)
    loan_page_urls: list[str] = field(default_factory=list)
    version: int = 1
    bypass_method: BypassMethod = BypassMethod.HEADLESS_BROWSER


@dataclass(frozen=True)
class LoanProgram:
    bank_id: int
    program_name: str
    loan_type: LoanType
    source_url: str
    id: Optional[int] = None
    min_interest_rate: Optional[float] = None
    max_interest_rate: Optional[float] = None
    min_amount: Optional[int] = None
    max_amount: Optional[int] = None
    min_tenure_months: Optional[int] = None
    max_tenure_months: Optional[int] = None
    rate_type: Optional[str] = None
    min_dp_percentage: Optional[float] = None
    data_confidence: float = 0.0
    completeness_score: float = 0.0


@dataclass(frozen=True)
class CrawlLog:
    bank_id: int
    strategy_id: int
    id: Optional[int] = None
    status: CrawlStatus = CrawlStatus.QUEUED
    programs_found: int = 0
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

_COMPLETENESS_FIELDS: tuple[str, ...] = (
    "program_name",
    "loan_type",
    "min_interest_rate",
    "max_interest_rate",
    "min_amount",
    "max_amount",
    "min_tenure_months",
    "max_tenure_months",
    "rate_type",
    "min_dp_percentage",
)


def calculate_completeness_score(data: dict) -> float:
    """Return the ratio of filled expected fields, rounded to 2 decimals."""
    total = len(_COMPLETENESS_FIELDS)
    if total == 0:
        return 0.0

    filled = sum(
        1 for f in _COMPLETENESS_FIELDS
        if data.get(f) is not None
    )
    return round(filled / total, 2)

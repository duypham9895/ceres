"""Verification scenarios and runtime smoke checks for CERES."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class VerificationScenario:
    """A declared verification scenario for CERES."""

    id: str
    category: str
    automation: str
    feature: str
    case_type: str
    command: str
    expected: str


VERIFICATION_SCENARIOS: tuple[VerificationScenario, ...] = (
    VerificationScenario(
        id="backend-suite",
        category="automated",
        automation="full",
        feature="backend regression",
        case_type="happy+worst",
        command="pytest -q",
        expected="All backend tests pass.",
    ),
    VerificationScenario(
        id="frontend-suite",
        category="automated",
        automation="full",
        feature="frontend regression",
        case_type="happy+worst",
        command="cd dashboard && npx vitest run",
        expected="All frontend tests pass.",
    ),
    VerificationScenario(
        id="frontend-build",
        category="automated",
        automation="full",
        feature="production build",
        case_type="happy",
        command="cd dashboard && npm run build",
        expected="Dashboard production bundle builds successfully.",
    ),
    VerificationScenario(
        id="docker-build",
        category="automated",
        automation="docker",
        feature="container rebuild",
        case_type="happy",
        command="docker compose build",
        expected="API, worker, and dashboard images build successfully.",
    ),
    VerificationScenario(
        id="docker-runtime",
        category="automated",
        automation="docker",
        feature="container startup",
        case_type="happy",
        command="docker compose up -d && docker compose ps",
        expected="Redis, API, worker, and dashboard are up; API is healthy.",
    ),
    VerificationScenario(
        id="api-smoke-happy",
        category="automated",
        automation="docker",
        feature="feature API smoke",
        case_type="happy",
        command="poetry run ceres verify --docker",
        expected="Core read APIs return valid payloads across dashboard features.",
    ),
    VerificationScenario(
        id="api-smoke-worst",
        category="automated",
        automation="docker",
        feature="feature API edge cases",
        case_type="worst",
        command="poetry run ceres verify --docker",
        expected="Invalid filters and unknown agents fail with expected 4xx responses.",
    ),
    VerificationScenario(
        id="single-bank-e2e",
        category="manual",
        automation="manual",
        feature="single-bank crawl/parse",
        case_type="happy",
        command="poetry run ceres crawler --bank <BANK> && poetry run ceres parser --bank <BANK>",
        expected="Raw pages and loan programs are created for a known bank.",
    ),
    VerificationScenario(
        id="all-bank-stability",
        category="manual",
        automation="manual",
        feature="all-bank pipeline stability",
        case_type="worst",
        command="poetry run ceres crawler && poetry run ceres parser",
        expected="No runaway browser processes, no stuck crawl logs, parser drains backlog.",
    ),
    VerificationScenario(
        id="schema-compatibility",
        category="manual",
        automation="manual",
        feature="database schema drift",
        case_type="worst",
        command="compare production schema against database/schema.sql before deploy",
        expected="New code does not rely on unmigrated columns or tables.",
    ),
    VerificationScenario(
        id="metrics-consistency",
        category="manual",
        automation="manual",
        feature="reporting integrity",
        case_type="worst",
        command="compare dashboard/API counts with loan_programs and crawl_logs tables",
        expected="Feature metrics match database reality.",
    ),
    VerificationScenario(
        id="release-schema-check",
        category="automated",
        automation="release",
        feature="database schema compatibility",
        case_type="worst",
        command="poetry run ceres verify-release",
        expected="Connected database exposes the required tables and columns for the current app version.",
    ),
    VerificationScenario(
        id="release-single-bank-smoke",
        category="semi-automated",
        automation="release",
        feature="single-bank live pipeline",
        case_type="happy",
        command="poetry run ceres verify-release --bank <BANK>",
        expected="Strategist, crawler, parser, and status complete for a real bank path.",
    ),
)


REQUIRED_SCHEMA: tuple[tuple[str, str], ...] = (
    ("banks", "bank_code"),
    ("banks", "website_status"),
    ("bank_strategies", "loan_page_urls"),
    ("bank_strategies", "success_rate"),
    ("crawl_logs", "programs_found"),
    ("crawl_logs", "pages_crawled"),
    ("crawl_raw_data", "parsed"),
    ("crawl_raw_data", "programs_produced"),
    ("loan_programs", "is_latest"),
    ("loan_programs", "min_tenor_months"),
    ("loan_programs", "max_tenor_months"),
    ("agent_runs", "agent_name"),
    ("agent_runs", "status"),
)


def run_api_smoke(base_url: str = "http://localhost:8000") -> None:
    """Run feature-level API smoke tests against a live CERES instance."""
    status = _get_json(f"{base_url}/api/status")
    if status.get("status") != "ok":
        raise RuntimeError("/api/status did not return status=ok")

    dashboard = _get_json(f"{base_url}/api/dashboard")
    _require_keys(dashboard, ("total_banks", "total_programs", "banks_by_status"))

    banks = _get_json(f"{base_url}/api/banks?page=1&limit=5")
    _require_keys(banks, ("data", "total", "page", "limit"))

    if banks["data"]:
        bank_id = banks["data"][0]["id"]
        bank_detail = _get_json(f"{base_url}/api/banks/{bank_id}")
        _require_keys(bank_detail, ("bank", "programs", "crawl_logs", "pipeline_status"))

    strategies = _get_json(f"{base_url}/api/strategies?page=1&limit=5")
    _require_keys(strategies, ("data", "total", "page", "limit"))

    programs = _get_json(f"{base_url}/api/loan-programs?page=1&limit=5")
    _require_keys(programs, ("data", "total", "page", "limit"))

    crawl_logs = _get_json(f"{base_url}/api/crawl-logs?page=1&limit=5")
    _require_keys(crawl_logs, ("data", "total", "page", "limit"))

    recommendations = _get_json(f"{base_url}/api/recommendations")
    _require_keys(recommendations, ("data",))

    latest_runs = _get_json(f"{base_url}/api/agent-runs/latest")
    _require_keys(latest_runs, ("data",))

    pipeline_health = _get_json(f"{base_url}/api/pipeline-health?days=7")
    _require_keys(pipeline_health, ("crawl", "parse", "strategies"))

    rates_heatmap = _get_json(f"{base_url}/api/rates/heatmap")
    _require_keys(rates_heatmap, ("banks",))

    rates_trend = _get_json(f"{base_url}/api/rates/trend?loan_type=KPR&days=7")
    _require_keys(rates_trend, ("loan_type", "series"))

    _expect_status(
        f"{base_url}/api/loan-programs?rate_min=10&rate_max=5",
        400,
    )
    _expect_status(
        f"{base_url}/api/loan-programs?date_from=bad-date",
        400,
    )
    _expect_status(
        f"{base_url}/api/banks/not-a-real-bank-code-or-uuid",
        404,
    )
    _expect_status(
        f"{base_url}/api/crawl/not-a-real-agent",
        400,
        method="POST",
    )


def _get_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return data


def _expect_status(url: str, expected_status: int, *, method: str = "GET") -> None:
    req = Request(url, method=method, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30):
            actual = 200
    except HTTPError as exc:
        actual = exc.code
    if actual != expected_status:
        raise RuntimeError(
            f"{method} {url} returned {actual}, expected {expected_status}"
        )


def _require_keys(data: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise RuntimeError(f"Response missing keys: {', '.join(missing)}")


async def assert_schema_compatibility(db: Any) -> None:
    """Fail if the connected DB is missing required tables/columns."""
    rows = await db.pool.fetch(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        """
    )
    existing = {
        (row["table_name"], row["column_name"])
        for row in rows
    }
    missing = [
        f"{table}.{column}"
        for table, column in REQUIRED_SCHEMA
        if (table, column) not in existing
    ]
    if missing:
        raise RuntimeError(
            "Database schema is missing required columns: "
            + ", ".join(sorted(missing))
        )

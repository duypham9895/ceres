from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse


def _iso(value: object) -> str | None:
    """Convert a datetime to ISO string; pass strings through unchanged."""
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)

router = APIRouter()

VALID_AGENTS = frozenset({
    "daily", "scout", "strategist", "crawler", "parser", "learning", "lab",
})

ALLOWED_LOAN_SORTS = frozenset({
    "program_name", "min_interest_rate", "max_interest_rate",
    "data_confidence", "completeness_score", "created_at",
})


def _paginated(data: list, *, total: int, page: int, limit: int) -> dict:
    """Build a pagination envelope without mutating inputs."""
    return {"data": data, "total": total, "page": page, "limit": limit}


def _error(message: str, *, code: str, status: int) -> JSONResponse:
    """Build an error envelope response."""
    return JSONResponse(
        {"error": message, "code": code},
        status_code=status,
    )


# ------------------------------------------------------------------
# Health / Status
# ------------------------------------------------------------------


@router.get("/status")
async def health_check(request: Request) -> dict:
    """Return service health status with current crawl job and last completed info."""
    runner = getattr(request.app.state, "task_runner", None)
    db = getattr(request.app.state, "db", None)
    current_job = runner.get_current_job() if runner else None
    step_info = runner.get_step_info() if runner else None

    current_job_data = None
    if current_job is not None:
        current_job_data = {
            "job_id": current_job.job_id,
            "agent": current_job.agent,
            "status": current_job.status.value if hasattr(current_job.status, 'value') else str(current_job.status),
            "started_at": _iso(current_job.started_at),
        }
        if step_info is not None:
            current_job_data = {**current_job_data, **step_info}

    # Fetch last completed crawl summary (time-window aggregation)
    last_completed = None
    if current_job is None and db is not None:
        row = await db.pool.fetchrow("""
            WITH latest AS (
                SELECT created_at FROM crawl_logs ORDER BY created_at DESC LIMIT 1
            )
            SELECT
                MAX(cl.created_at) AS finished_at,
                COUNT(*) FILTER (WHERE cl.status = 'SUCCESS') AS success_count,
                COUNT(*) AS total_count
            FROM crawl_logs cl
            WHERE cl.created_at >= (SELECT created_at - INTERVAL '30 minutes' FROM latest)
        """)
        if row is not None and row["total_count"] is not None and row["total_count"] > 0:
            last_completed = {
                "finished_at": _iso(row["finished_at"]),
                "success_count": row["success_count"],
                "total_count": row["total_count"],
            }

    return {
        "status": "ok",
        "current_job": current_job_data,
        "last_completed": last_completed,
    }


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------


@router.get("/dashboard")
async def dashboard_overview(request: Request) -> dict:
    """Overview stats: total banks by status, programs count, 7-day success rate."""
    db = request.app.state.db

    banks = await db.fetch_banks()
    programs = await db.fetch_loan_programs()
    stats = await db.get_crawl_stats()

    total_crawls = stats.get("total_crawls", 0)
    successes = stats.get("successes", 0)
    success_rate = successes / total_crawls if total_crawls > 0 else 0.0

    # Count banks by status without mutation
    status_counts: dict[str, int] = {}
    for bank in banks:
        ws = bank.get("website_status", "unknown")
        status_counts = {**status_counts, ws: status_counts.get(ws, 0) + 1}

    return {
        "total_banks": len(banks),
        "total_programs": len(programs),
        "banks_by_status": status_counts,
        "success_rate": success_rate,
        "crawl_stats": stats,
    }


# ------------------------------------------------------------------
# Banks
# ------------------------------------------------------------------


@router.get("/banks")
async def list_banks(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
) -> dict:
    """Paginated bank list with optional category filter, includes program count."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = []
    params: list = []
    param_idx = 1

    if category is not None:
        conditions.append(f"b.bank_category = ${param_idx}")
        params.append(category)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_query = f"SELECT COUNT(*) FROM banks b {where}"
    total = await db.pool.fetchval(count_query, *params)

    data_query = f"""
        SELECT b.*, COUNT(lp.id) AS programs_count
        FROM banks b
        LEFT JOIN loan_programs lp ON lp.bank_id = b.id AND lp.is_latest = true
        {where}
        GROUP BY b.id
        ORDER BY b.bank_code
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    rows = await db.pool.fetch(data_query, *params, limit, offset)

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


@router.get("/banks/{bank_id}", response_model=None)
async def get_bank_detail(request: Request, bank_id: str):
    """Bank detail with programs, strategies, and recent crawl logs."""
    db = request.app.state.db

    # Try UUID lookup first, fall back to bank_code
    try:
        UUID(bank_id)
        bank = await db.pool.fetchrow(
            "SELECT * FROM banks WHERE id = $1::uuid", bank_id,
        )
    except ValueError:
        bank = await db.pool.fetchrow(
            "SELECT * FROM banks WHERE bank_code = $1", bank_id,
        )
    if bank is None:
        return _error("Bank not found", code="NOT_FOUND", status=404)

    bid = str(bank["id"])
    programs = await db.fetch_loan_programs(bank_id=bid)
    strategies = await db.fetch_active_strategies(bank_id=bid)
    crawl_logs = await db.pool.fetch(
        """
        SELECT cl.*, cl.created_at AS started_at, b.bank_code
        FROM crawl_logs cl
        JOIN banks b ON b.id = cl.bank_id
        WHERE cl.bank_id = $1::uuid
        ORDER BY cl.created_at DESC
        LIMIT 20
        """,
        bid,
    )

    strategy = dict(strategies[0]) if strategies else None

    raw_data_stats = await db.pool.fetchrow(
        """
        SELECT
            COUNT(*) AS total_pages,
            COUNT(*) FILTER (WHERE parsed = true) AS parsed_pages,
            COUNT(*) FILTER (WHERE parsed = false) AS unparsed_pages
        FROM crawl_raw_data
        WHERE bank_id = $1::uuid
        """,
        bid,
    )

    last_crawl = crawl_logs[0] if crawl_logs else None
    pipeline_status = {
        "crawl": {
            "status": last_crawl["status"] if last_crawl else "never",
            "pages": raw_data_stats["total_pages"],
            "last_run": last_crawl["created_at"].isoformat() if last_crawl else None,
        },
        "parse": {
            "total": raw_data_stats["total_pages"],
            "parsed": raw_data_stats["parsed_pages"],
            "unparsed": raw_data_stats["unparsed_pages"],
        },
        "extract": {
            "programs": len(programs),
        },
    }

    return {
        "bank": dict(bank),
        "strategy": strategy,
        "programs": [dict(p) for p in programs],
        "crawl_logs": [dict(cl) for cl in crawl_logs],
        "pipeline_status": pipeline_status,
    }


# ------------------------------------------------------------------
# Crawl Logs
# ------------------------------------------------------------------


@router.get("/crawl-logs")
async def list_crawl_logs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    bank_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> dict:
    """Paginated crawl logs with status, bank_id, and date filters."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = []
    params: list = []
    param_idx = 1

    if status is not None:
        conditions.append(f"cl.status = ${param_idx}")
        params.append(status)
        param_idx += 1

    if bank_id is not None:
        conditions.append(f"cl.bank_id = ${param_idx}::uuid")
        params.append(bank_id)
        param_idx += 1

    if date_from is not None:
        conditions.append(f"cl.created_at >= ${param_idx}::timestamptz")
        params.append(date_from)
        param_idx += 1

    if date_to is not None:
        conditions.append(f"cl.created_at <= ${param_idx}::timestamptz")
        params.append(date_to)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM crawl_logs cl JOIN banks b ON b.id = cl.bank_id {where}", *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT cl.*, cl.created_at AS started_at, b.bank_code
        FROM crawl_logs cl
        JOIN banks b ON b.id = cl.bank_id
        {where}
        ORDER BY cl.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


# ------------------------------------------------------------------
# Loan Programs
# ------------------------------------------------------------------


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_EXPORT_ROWS = 10_000


def _build_loan_program_query(
    *,
    bank_id: Optional[str],
    loan_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[str, list, int]:
    """Build WHERE clause for loan_programs queries. Returns (where, params, next_param_idx)."""
    conditions: list[str] = ["lp.is_latest = true"]
    params: list = []
    param_idx = 1

    if bank_id is not None:
        conditions.append(f"lp.bank_id = ${param_idx}::uuid")
        params.append(bank_id)
        param_idx += 1

    if loan_type is not None:
        conditions.append(f"lp.loan_type = ${param_idx}")
        params.append(loan_type)
        param_idx += 1

    if date_from is not None:
        conditions.append(f"lp.created_at >= ${param_idx}::date")
        params.append(date_from)
        param_idx += 1

    if date_to is not None:
        conditions.append(f"lp.created_at < (${param_idx}::date + interval '1 day')")
        params.append(date_to)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}"
    return where, params, param_idx


@router.get("/loan-programs")
async def list_loan_programs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    bank_id: Optional[str] = Query(None),
    loan_type: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> dict:
    """Paginated loan programs with bank_id, loan_type, date range, and sort params."""
    for label, val in [("date_from", date_from), ("date_to", date_to)]:
        if val is not None and not _DATE_RE.match(val):
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid {label} format. Use YYYY-MM-DD."},
            )

    db = request.app.state.db
    offset = (page - 1) * limit

    where, params, param_idx = _build_loan_program_query(
        bank_id=bank_id, loan_type=loan_type, date_from=date_from, date_to=date_to,
    )

    # Validate sort column
    order_col = "lp.program_name"
    if sort is not None and sort in ALLOWED_LOAN_SORTS:
        order_col = f"lp.{sort}"

    total = await db.pool.fetchval(
        f"""SELECT COUNT(*) FROM loan_programs lp
            JOIN banks b ON b.id = lp.bank_id
            {where}""",
        *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT lp.*, b.bank_code FROM loan_programs lp
        JOIN banks b ON b.id = lp.bank_id
        {where}
        ORDER BY {order_col}
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


@router.get("/loan-programs/export")
async def export_loan_programs(
    request: Request,
    bank_id: Optional[str] = Query(None),
    loan_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> StreamingResponse:
    """Export loan programs as XLSX with current filters applied."""
    for label, val in [("date_from", date_from), ("date_to", date_to)]:
        if val is not None and not _DATE_RE.match(val):
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid {label} format. Use YYYY-MM-DD."},
            )

    db = request.app.state.db

    where, params, _ = _build_loan_program_query(
        bank_id=bank_id, loan_type=loan_type, date_from=date_from, date_to=date_to,
    )

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM loan_programs lp {where}", *params,
    )
    if total > MAX_EXPORT_ROWS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Too many rows ({total}). Apply filters to narrow the export."},
        )

    rows = await db.pool.fetch(
        f"""
        SELECT lp.program_name, b.bank_code, lp.loan_type,
               lp.min_interest_rate, lp.max_interest_rate,
               lp.min_amount, lp.max_amount,
               lp.min_tenor_months, lp.max_tenor_months,
               lp.data_confidence, lp.completeness_score,
               lp.source_url, lp.created_at
        FROM loan_programs lp
        JOIN banks b ON b.id = lp.bank_id
        {where}
        ORDER BY b.bank_code, lp.program_name
        """,
        *params,
    )

    from openpyxl import Workbook

    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append([
        "Program Name", "Bank", "Loan Type",
        "Min Rate (%)", "Max Rate (%)",
        "Min Amount", "Max Amount",
        "Min Tenor (mo)", "Max Tenor (mo)",
        "Confidence", "Completeness",
        "Source URL", "Created At",
    ])
    for r in rows:
        ws.append([
            r["program_name"], r["bank_code"], r["loan_type"],
            float(r["min_interest_rate"]) if r["min_interest_rate"] else None,
            float(r["max_interest_rate"]) if r["max_interest_rate"] else None,
            float(r["min_amount"]) if r["min_amount"] else None,
            float(r["max_amount"]) if r["max_amount"] else None,
            r["min_tenor_months"], r["max_tenor_months"],
            float(r["data_confidence"]) if r["data_confidence"] else None,
            float(r["completeness_score"]) if r["completeness_score"] else None,
            r["source_url"],
            r["created_at"].isoformat() if r["created_at"] else None,
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="loan-programs-{today}.xlsx"'},
    )


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------


@router.get("/strategies")
async def list_strategies(request: Request) -> dict:
    """All active strategies joined with bank info."""
    db = request.app.state.db

    rows = await db.pool.fetch(
        """
        SELECT bs.*, b.bank_code, b.bank_name
        FROM bank_strategies bs
        JOIN banks b ON b.id = bs.bank_id
        WHERE bs.is_active = true
        ORDER BY b.bank_code
        """
    )

    return {"data": [dict(r) for r in rows]}


# ------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------


@router.get("/recommendations")
async def list_recommendations(request: Request) -> dict:
    """All recommendations ordered by priority."""
    db = request.app.state.db

    rows = await db.pool.fetch(
        "SELECT * FROM ringkas_recommendations ORDER BY priority ASC"
    )

    return {"data": [dict(r) for r in rows]}


# ------------------------------------------------------------------
# Agent Runs
# ------------------------------------------------------------------


@router.get("/agent-runs/latest")
async def latest_agent_runs(request: Request) -> dict:
    """Most recent run per agent for dashboard status display."""
    db = request.app.state.db
    rows = await db.get_latest_agent_runs()
    return {"data": rows}


# ------------------------------------------------------------------
# Rate Intelligence
# ------------------------------------------------------------------


@router.get("/rates/heatmap")
async def rates_heatmap(request: Request) -> dict:
    """Rate heatmap: all banks with min interest rates by loan type."""
    db = request.app.state.db

    rows = await db.pool.fetch(
        """
        SELECT b.id AS bank_id, b.bank_code, b.bank_name, b.website_status,
               lp.loan_type, MIN(lp.min_interest_rate) AS min_rate
        FROM banks b
        LEFT JOIN loan_programs lp ON lp.bank_id = b.id AND lp.is_latest = true
        GROUP BY b.id, b.bank_code, b.bank_name, b.website_status, lp.loan_type
        ORDER BY b.bank_code
        """
    )

    banks: dict[str, dict] = {}
    for row in rows:
        code = row["bank_code"]
        if code not in banks:
            banks[code] = {
                "bank_id": str(row["bank_id"]),
                "bank_code": code,
                "bank_name": row["bank_name"],
                "website_status": row["website_status"],
                "rates": {},
            }
        if row["loan_type"] and row["min_rate"] is not None:
            banks[code]["rates"][row["loan_type"]] = float(row["min_rate"])

    return {"banks": list(banks.values())}


@router.get("/rates/trend")
async def rates_trend(
    request: Request,
    loan_type: str = Query("KPR"),
    days: int = Query(7, ge=1, le=30),
) -> dict:
    """Daily average min interest rate for a loan type over N days."""
    db = request.app.state.db

    rows = await db.pool.fetch(
        """
        SELECT DATE(lp.updated_at) AS date,
               AVG(lp.min_interest_rate) AS avg_min_rate
        FROM loan_programs lp
        WHERE lp.loan_type = $1
          AND lp.is_latest = true
          AND lp.updated_at >= NOW() - make_interval(days => $2)
          AND lp.min_interest_rate IS NOT NULL
        GROUP BY DATE(lp.updated_at)
        ORDER BY date
        """,
        loan_type,
        days,
    )

    return {
        "loan_type": loan_type,
        "series": [
            {"date": str(r["date"]), "avg_min_rate": float(r["avg_min_rate"])}
            for r in rows
        ],
    }


# ------------------------------------------------------------------
# Crawl Triggers (Write)
# ------------------------------------------------------------------


@router.post("/crawl/{agent_name}")
async def trigger_crawl(
    request: Request,
    agent_name: str,
    bank: Optional[str] = Query(None),
) -> JSONResponse:
    """Trigger a crawl job. Returns 202 on success, 409 if busy, 400 if unknown agent."""
    if agent_name not in VALID_AGENTS:
        return _error(
            f"Unknown agent: {agent_name}",
            code="INVALID_AGENT",
            status=400,
        )

    runner = request.app.state.task_runner

    kwargs: dict = {}
    if bank is not None:
        kwargs["bank_code"] = bank

    job = await runner.start_job(agent_name, **kwargs)

    if job is None:
        return _error(
            "A crawl job is already running",
            code="JOB_ALREADY_RUNNING",
            status=409,
        )

    return JSONResponse(
        {
            "job_id": job.job_id,
            "agent": job.agent,
            "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            "started_at": _iso(job.started_at),
        },
        status_code=202,
    )

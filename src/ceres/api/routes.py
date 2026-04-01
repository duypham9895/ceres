from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse


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

    bank = await db.pool.fetchrow(
        "SELECT * FROM banks WHERE id = $1::uuid", bank_id,
    )
    if bank is None:
        return _error("Bank not found", code="NOT_FOUND", status=404)

    programs = await db.fetch_loan_programs(bank_id=bank_id)
    strategies = await db.fetch_active_strategies(bank_id=bank_id)
    crawl_logs = await db.pool.fetch(
        """
        SELECT * FROM crawl_logs
        WHERE bank_id = $1::uuid
        ORDER BY created_at DESC
        LIMIT 20
        """,
        bank_id,
    )

    return {
        "bank": dict(bank),
        "programs": [dict(p) for p in programs],
        "strategies": [dict(s) for s in strategies],
        "recent_crawl_logs": [dict(cl) for cl in crawl_logs],
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
        conditions.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1

    if bank_id is not None:
        conditions.append(f"bank_id = ${param_idx}::uuid")
        params.append(bank_id)
        param_idx += 1

    if date_from is not None:
        conditions.append(f"created_at >= ${param_idx}::timestamptz")
        params.append(date_from)
        param_idx += 1

    if date_to is not None:
        conditions.append(f"created_at <= ${param_idx}::timestamptz")
        params.append(date_to)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM crawl_logs {where}", *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT * FROM crawl_logs {where}
        ORDER BY created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


# ------------------------------------------------------------------
# Loan Programs
# ------------------------------------------------------------------


@router.get("/loan-programs")
async def list_loan_programs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    bank_id: Optional[str] = Query(None),
    loan_type: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
) -> dict:
    """Paginated loan programs with bank_id, loan_type, and sort params."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = ["is_latest = true"]
    params: list = []
    param_idx = 1

    if bank_id is not None:
        conditions.append(f"bank_id = ${param_idx}::uuid")
        params.append(bank_id)
        param_idx += 1

    if loan_type is not None:
        conditions.append(f"loan_type = ${param_idx}")
        params.append(loan_type)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}"

    # Validate sort column
    order_col = "program_name"
    if sort is not None and sort in ALLOWED_LOAN_SORTS:
        order_col = sort

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM loan_programs {where}", *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT * FROM loan_programs {where}
        ORDER BY {order_col}
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


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

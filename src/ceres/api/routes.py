from __future__ import annotations

import io
import re
from datetime import date, datetime
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


def _add_multi_filter(
    conditions: list[str], params: list, param_idx: int,
    column: str, value: str | None,
) -> int:
    """Add a multi-value filter (comma-separated) or single-value filter.

    Returns the next param_idx to use.
    """
    if value is None:
        return param_idx
    values = [v.strip() for v in value.split(",") if v.strip()]
    if not values:
        return param_idx
    if len(values) == 1:
        conditions.append(f"{column} = ${param_idx}")
        params.append(values[0])
    else:
        conditions.append(f"{column} = ANY(${param_idx}::text[])")
        params.append(values)
    return param_idx + 1


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
    quality = await db.get_dashboard_quality()
    sparklines = await db.get_dashboard_sparklines()

    total_crawls = stats.get("total_crawls", 0)
    successes = stats.get("successful", 0)
    success_rate = successes / total_crawls if total_crawls > 0 else 0.0

    # Count banks by status without mutation
    status_counts: dict[str, int] = {}
    for bank in banks:
        ws = bank.get("website_status", "unknown")
        status_counts = {**status_counts, ws: status_counts.get(ws, 0) + 1}

    # Compute deltas from sparkline series (last vs second-to-last value)
    banks_series = sparklines.get("banks", [])
    programs_series = sparklines.get("programs", [])
    kpr_series = sparklines.get("kpr_rate", [])
    quality_series = sparklines.get("quality", [])

    banks_week = (banks_series[-1] - banks_series[-8]) if len(banks_series) >= 8 else 0
    programs_new = stats.get("new_programs", 0)
    kpr_rate_change = (
        round(kpr_series[-1] - kpr_series[-2], 4) if len(kpr_series) >= 2 else 0.0
    )
    quality_change = (
        round(quality_series[-1] - quality_series[-2], 4) if len(quality_series) >= 2 else 0.0
    )

    return {
        "total_banks": len(banks),
        "total_programs": len(programs),
        "banks_by_status": status_counts,
        "success_rate": success_rate,
        "crawl_stats": stats,
        "quality_avg": quality,
        "sparklines": sparklines,
        "deltas": {
            "banks_week": banks_week,
            "programs_new": programs_new,
            "kpr_rate_change": kpr_rate_change,
            "quality_change": quality_change,
        },
    }


@router.get("/dashboard/alerts")
async def dashboard_alerts(request: Request) -> dict:
    """Dashboard alert counts grouped by severity."""
    db = request.app.state.db
    alerts = await db.get_dashboard_alerts()
    total = sum(a["count"] for a in alerts)
    return {"total": total, "alerts": alerts}


@router.get("/dashboard/changes")
async def dashboard_changes(request: Request) -> dict:
    """Loan program changes detected today."""
    db = request.app.state.db
    today = date.today()
    changes = await db.get_dashboard_changes(today)
    return {"date": today.isoformat(), "changes": changes}


@router.get("/dashboard/quality")
async def dashboard_quality(request: Request) -> dict:
    """Overall data quality metrics."""
    db = request.app.state.db
    return await db.get_dashboard_quality()


# ------------------------------------------------------------------
# Banks
# ------------------------------------------------------------------


@router.get("/banks")
async def list_banks(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    website_status: Optional[str] = Query(None),
) -> dict:
    """Paginated bank list with optional category and website_status filters, includes program count."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = []
    params: list = []
    param_idx = 1

    param_idx = _add_multi_filter(conditions, params, param_idx, "b.bank_category", category)
    param_idx = _add_multi_filter(conditions, params, param_idx, "b.website_status", website_status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_query = f"SELECT COUNT(*) FROM banks b {where}"
    total = await db.pool.fetchval(count_query, *params)

    data_query = f"""
        SELECT
            b.*,
            COUNT(lp.id) AS programs_count,
            b.crawl_streak,
            COALESCE(
                (
                    SELECT ROUND(
                        COUNT(*) FILTER (WHERE cl30.status = 'SUCCESS')::numeric /
                        NULLIF(COUNT(*), 0), 4
                    )
                    FROM crawl_logs cl30
                    WHERE cl30.bank_id = b.id
                      AND cl30.created_at >= NOW() - INTERVAL '30 days'
                ),
                0.0
            ) AS success_rate_30d,
            COALESCE(
                (
                    SELECT ROUND(AVG(lp_q.completeness_score)::numeric, 4)
                    FROM loan_programs lp_q
                    WHERE lp_q.bank_id = b.id AND lp_q.is_latest = true
                ),
                0.0
            ) AS avg_quality
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

    # Compute success_rate_30d and avg_quality for the bank detail view
    health_stats = await db.pool.fetchrow(
        """
        SELECT
            COALESCE(
                (
                    SELECT ROUND(
                        COUNT(*) FILTER (WHERE cl30.status = 'SUCCESS')::numeric /
                        NULLIF(COUNT(*), 0), 4
                    )
                    FROM crawl_logs cl30
                    WHERE cl30.bank_id = $1::uuid
                      AND cl30.created_at >= NOW() - INTERVAL '30 days'
                ),
                0.0
            ) AS success_rate_30d,
            COALESCE(
                (
                    SELECT ROUND(AVG(lp_q.completeness_score)::numeric, 4)
                    FROM loan_programs lp_q
                    WHERE lp_q.bank_id = $1::uuid AND lp_q.is_latest = true
                ),
                0.0
            ) AS avg_quality,
            COALESCE(
                (
                    SELECT ROUND(AVG(lp_q.data_confidence)::numeric, 4)
                    FROM loan_programs lp_q
                    WHERE lp_q.bank_id = $1::uuid AND lp_q.is_latest = true
                ),
                0.0
            ) AS avg_confidence
        """,
        bid,
    )

    bank_dict = dict(bank)
    if health_stats:
        bank_dict["success_rate_30d"] = float(health_stats["success_rate_30d"])
        bank_dict["avg_quality"] = float(health_stats["avg_quality"])
        bank_dict["avg_confidence"] = float(health_stats["avg_confidence"])
    else:
        bank_dict["success_rate_30d"] = 0.0
        bank_dict["avg_quality"] = 0.0
        bank_dict["avg_confidence"] = 0.0

    return {
        "bank": bank_dict,
        "strategy": strategy,
        "programs": [dict(p) for p in programs],
        "crawl_logs": [dict(cl) for cl in crawl_logs],
        "pipeline_status": pipeline_status,
    }


# ------------------------------------------------------------------
# Crawl Logs
# ------------------------------------------------------------------


@router.get("/crawl-logs/analytics")
async def crawl_log_analytics(
    request: Request,
    days: int = Query(7, ge=1, le=90),
) -> dict:
    """Aggregated crawl analytics over N days."""
    db = request.app.state.db
    return await db.get_crawl_analytics(days=days)


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

    param_idx = _add_multi_filter(conditions, params, param_idx, "cl.status", status)

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


@router.get("/loan-programs/compare")
async def loan_programs_compare(
    request: Request,
    loan_type: str = Query(...),
) -> dict:
    """Compare loan programs across banks for a given loan type."""
    db = request.app.state.db
    programs = await db.get_loan_compare(loan_type)
    return {"loan_type": loan_type, "programs": programs}


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_EXPORT_ROWS = 10_000


def _build_loan_program_query(
    *,
    bank_id: Optional[str],
    loan_type: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    rate_min: Optional[float] = None,
    rate_max: Optional[float] = None,
) -> tuple[str, list, int]:
    """Build WHERE clause for loan_programs queries. Returns (where, params, next_param_idx)."""
    conditions: list[str] = ["lp.is_latest = true"]
    params: list = []
    param_idx = 1

    if bank_id is not None:
        conditions.append(f"lp.bank_id = ${param_idx}::uuid")
        params.append(bank_id)
        param_idx += 1

    param_idx = _add_multi_filter(conditions, params, param_idx, "lp.loan_type", loan_type)

    if date_from is not None:
        conditions.append(f"lp.created_at >= ${param_idx}::date")
        params.append(date_from)
        param_idx += 1

    if date_to is not None:
        conditions.append(f"lp.created_at < (${param_idx}::date + interval '1 day')")
        params.append(date_to)
        param_idx += 1

    if rate_min is not None:
        conditions.append(f"lp.min_interest_rate >= ${param_idx}")
        params.append(rate_min)
        param_idx += 1

    if rate_max is not None:
        conditions.append(f"lp.max_interest_rate <= ${param_idx}")
        params.append(rate_max)
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
    rate_min: Optional[float] = Query(None),
    rate_max: Optional[float] = Query(None),
) -> dict:
    """Paginated loan programs with bank_id, loan_type, date range, rate range, and sort params."""
    for label, val in [("date_from", date_from), ("date_to", date_to)]:
        if val is not None and not _DATE_RE.match(val):
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid {label} format. Use YYYY-MM-DD."},
            )

    if rate_min is not None and rate_max is not None and rate_min > rate_max:
        return _error(
            "rate_min must be less than or equal to rate_max",
            code="INVALID_RATE_RANGE",
            status=400,
        )

    db = request.app.state.db
    offset = (page - 1) * limit

    where, params, param_idx = _build_loan_program_query(
        bank_id=bank_id, loan_type=loan_type, date_from=date_from, date_to=date_to,
        rate_min=rate_min, rate_max=rate_max,
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
        SELECT lp.*,
               b.bank_code,
               lp.rate_fixed,
               lp.rate_floating,
               lp.rate_promo,
               lp.rate_promo_duration_months
        FROM loan_programs lp
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
    rate_min: Optional[float] = Query(None),
    rate_max: Optional[float] = Query(None),
) -> StreamingResponse:
    """Export loan programs as XLSX with current filters applied."""
    for label, val in [("date_from", date_from), ("date_to", date_to)]:
        if val is not None and not _DATE_RE.match(val):
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid {label} format. Use YYYY-MM-DD."},
            )

    if rate_min is not None and rate_max is not None and rate_min > rate_max:
        return _error(
            "rate_min must be less than or equal to rate_max",
            code="INVALID_RATE_RANGE",
            status=400,
        )

    db = request.app.state.db

    where, params, _ = _build_loan_program_query(
        bank_id=bank_id, loan_type=loan_type, date_from=date_from, date_to=date_to,
        rate_min=rate_min, rate_max=rate_max,
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
async def list_strategies(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    bank_id: Optional[str] = Query(None),
    success_rate_min: Optional[float] = Query(None),
    success_rate_max: Optional[float] = Query(None),
) -> dict:
    """Paginated active strategies with optional bank_id and success_rate filters."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = ["bs.is_active = true"]
    params: list = []
    param_idx = 1

    if bank_id is not None:
        bank_ids = [v.strip() for v in bank_id.split(",") if v.strip()]
        if len(bank_ids) == 1:
            conditions.append(f"bs.bank_id = ${param_idx}::uuid")
            params.append(bank_ids[0])
        else:
            conditions.append(f"bs.bank_id = ANY(${param_idx}::uuid[])")
            params.append(bank_ids)
        param_idx += 1

    if success_rate_min is not None:
        conditions.append(f"bs.success_rate >= ${param_idx}")
        params.append(success_rate_min)
        param_idx += 1

    if success_rate_max is not None:
        conditions.append(f"bs.success_rate <= ${param_idx}")
        params.append(success_rate_max)
        param_idx += 1

    where = f"WHERE {' AND '.join(conditions)}"

    total = await db.pool.fetchval(
        f"""SELECT COUNT(*) FROM bank_strategies bs
            JOIN banks b ON b.id = bs.bank_id
            {where}""",
        *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT bs.*, b.bank_code, b.bank_name
        FROM bank_strategies bs
        JOIN banks b ON b.id = bs.bank_id
        {where}
        ORDER BY b.bank_code
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    # Fetch 30-day daily success trends for each strategy's bank
    bank_ids = list({str(r["bank_id"]) for r in rows})
    trend_rows: list = []
    if bank_ids:
        trend_rows = await db.pool.fetch(
            """
            SELECT
                cl.bank_id::text,
                DATE(cl.created_at) AS day,
                ROUND(
                    COUNT(*) FILTER (WHERE cl.status = 'SUCCESS')::numeric /
                    NULLIF(COUNT(*), 0), 4
                ) AS rate
            FROM crawl_logs cl
            WHERE cl.bank_id = ANY($1::uuid[])
              AND cl.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY cl.bank_id, DATE(cl.created_at)
            ORDER BY cl.bank_id, day
            """,
            bank_ids,
        )

    # Build bank_id -> list of daily rates mapping
    trend_map: dict[str, list[float]] = {}
    for tr in trend_rows:
        bid = tr["bank_id"]
        trend_map[bid] = [*trend_map.get(bid, []), float(tr["rate"])]

    data = [
        {**dict(r), "success_trend": trend_map.get(str(r["bank_id"]), [])}
        for r in rows
    ]

    return _paginated(data, total=total, page=page, limit=limit)


# ------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------


ALLOWED_REC_SORTS = frozenset({"priority", "created_at", "updated_at", "status"})


@router.get("/recommendations")
async def list_recommendations(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
) -> dict:
    """Paginated recommendations with optional status filter and sort."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions: list[str] = []
    params: list = []
    param_idx = 1

    param_idx = _add_multi_filter(conditions, params, param_idx, "status", status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_col = "priority"
    if sort is not None and sort in ALLOWED_REC_SORTS:
        order_col = sort

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM ringkas_recommendations {where}", *params,
    )

    rows = await db.pool.fetch(
        f"""
        SELECT * FROM ringkas_recommendations
        {where}
        ORDER BY {order_col} ASC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return _paginated([dict(r) for r in rows], total=total, page=page, limit=limit)


@router.patch("/recommendations/{rec_id}")
async def update_recommendation(request: Request, rec_id: UUID):
    """Update status and/or status_note on a recommendation."""
    body = await request.json()
    status = body.get("status")
    status_note = body.get("status_note")
    valid_statuses = {"pending", "reviewed", "in_progress", "done", "dismissed"}
    if status and status not in valid_statuses:
        return _error(f"Invalid status: {status}", code="INVALID_STATUS", status=400)
    db = request.app.state.db
    result = await db.update_recommendation(rec_id, status=status, status_note=status_note)
    if not result:
        return _error("Recommendation not found", code="NOT_FOUND", status=404)
    return result


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
# Pipeline Health
# ------------------------------------------------------------------


_FAILING_THRESHOLD = 0.3


@router.get("/pipeline-health")
async def pipeline_health(
    request: Request,
    days: int = Query(7, ge=1, le=90),
) -> dict:
    """Pipeline health metrics: crawl and parse success rates per bank, strategy health."""
    db = request.app.state.db

    crawl_stats = await db.get_crawl_stats(days=days)
    bank_crawl_stats = await db.get_bank_crawl_stats(days=days)
    parse_stats = await db.get_parse_stats(days=days)
    strategies = await db.fetch_active_strategies()

    total_crawls = crawl_stats.get("total_crawls", 0)
    successful_crawls = crawl_stats.get("successful", 0)
    crawl_success_rate = (
        successful_crawls / total_crawls if total_crawls > 0 else 0.0
    )

    crawl_by_bank = [
        {
            "bank_code": row["bank_code"],
            "success_rate": (
                row["successful"] / row["total_crawls"]
                if row["total_crawls"] > 0
                else 0.0
            ),
            "total": row["total_crawls"],
            "failed": row["failed"],
            "blocked": row["blocked"],
        }
        for row in bank_crawl_stats
    ]

    total_raw = sum(row["total_raw_rows"] for row in parse_stats)
    total_with_programs = sum(row["rows_with_programs"] for row in parse_stats)
    parse_success_rate = (
        total_with_programs / total_raw if total_raw > 0 else 0.0
    )

    parse_by_bank = [
        {
            "bank_code": row["bank_code"],
            "total": row["total_raw_rows"],
            "parsed": row["parsed_rows"],
            "with_programs": row["rows_with_programs"],
            "success_rate": (
                row["rows_with_programs"] / row["total_raw_rows"]
                if row["total_raw_rows"] > 0
                else 0.0
            ),
        }
        for row in parse_stats
    ]

    active_strategies = [dict(s) for s in strategies]
    rates = [
        float(s.get("success_rate", 0))
        for s in active_strategies
        if s.get("success_rate") is not None
    ]
    avg_success_rate = sum(rates) / len(rates) if rates else 0.0

    failing = [
        {
            "bank_code": s.get("bank_code"),
            "success_rate": float(s.get("success_rate", 0)),
            "anti_bot_detected": s.get("anti_bot_detected", False),
        }
        for s in active_strategies
        if float(s.get("success_rate", 0)) < _FAILING_THRESHOLD
    ]

    return {
        "crawl": {
            "overall_success_rate": round(crawl_success_rate, 4),
            "total_crawls": total_crawls,
            "by_bank": crawl_by_bank,
        },
        "parse": {
            "overall_success_rate": round(parse_success_rate, 4),
            "total_raw_rows": total_raw,
            "by_bank": parse_by_bank,
        },
        "strategies": {
            "total_active": len(active_strategies),
            "avg_success_rate": round(avg_success_rate, 4),
            "failing": failing,
        },
    }


# ------------------------------------------------------------------
# Rate Intelligence
# ------------------------------------------------------------------


@router.get("/rates/heatmap")
async def rates_heatmap(
    request: Request,
    loan_type: Optional[str] = Query(None),
) -> dict:
    """Rate heatmap: all banks with min interest rates by loan type."""
    db = request.app.state.db

    loan_filter = ""
    params: list = []
    if loan_type and loan_type.upper() != "ALL":
        loan_filter = "AND lp.loan_type = $1"
        params.append(loan_type.upper())

    rows = await db.pool.fetch(
        f"""
        SELECT b.id AS bank_id, b.bank_code, b.bank_name, b.website_status,
               lp.loan_type, MIN(lp.min_interest_rate) AS min_rate,
               ROUND(AVG(lp.completeness_score)::numeric, 4) AS completeness_score,
               ROUND(AVG(lp.data_confidence)::numeric, 4) AS data_confidence
        FROM banks b
        LEFT JOIN loan_programs lp ON lp.bank_id = b.id AND lp.is_latest = true
            {loan_filter}
        GROUP BY b.id, b.bank_code, b.bank_name, b.website_status, lp.loan_type
        ORDER BY b.bank_code
        """,
        *params,
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
                "completeness_score": (
                    float(row["completeness_score"]) if row["completeness_score"] is not None else None
                ),
                "data_confidence": (
                    float(row["data_confidence"]) if row["data_confidence"] is not None else None
                ),
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


@router.post("/strategies/rebuild-all")
async def rebuild_all_strategies(request: Request) -> JSONResponse:
    """Enqueue strategy rebuild for all active banks with force=True.

    Uses batch enqueue when arq is available for a single Redis round-trip.
    """
    db = request.app.state.db
    runner = request.app.state.task_runner

    banks = await db.fetch_banks()
    active_banks = [b for b in banks if b.get("website_status") in ("active", "unknown")]

    jobs = await runner.enqueue_batch(
        agent="strategist",
        bank_codes=[b["bank_code"] for b in active_banks],
        force=True,
    )

    queued = sum(1 for j in jobs if j is not None)
    failed_banks = [
        b["bank_code"]
        for b, j in zip(active_banks, jobs)
        if j is None
    ]

    return JSONResponse(
        {"queued": queued, "total_banks": len(active_banks), "failed": failed_banks},
        status_code=202,
    )


@router.post("/crawl/{agent_name}")
async def trigger_crawl(
    request: Request,
    agent_name: str,
    bank: Optional[str] = Query(None),
    force: bool = Query(False),
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

    job = await runner.start_job(agent_name, force=force, **kwargs)

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

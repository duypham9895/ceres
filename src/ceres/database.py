"""Async database module for CERES using asyncpg."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Data quality constants
MIN_CONFIDENCE_THRESHOLD = 0.4
MIN_RATE_BOUND = 0.1
MAX_RATE_BOUND = 30.0


class Database:
    """Async PostgreSQL database client wrapping an asyncpg connection pool."""

    def __init__(self, dsn: str, *, min_size: int = 2, max_size: int = 10) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self.pool: Optional[asyncpg.Pool] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the connection pool."""
        self.pool = await asyncpg.create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            # Use default statement cache (100) for prepared statement reuse;
            # cache_size=0 was previously set to work around pgbouncer but
            # we connect directly to Postgres so caching improves performance.
        )

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    # ------------------------------------------------------------------
    # Banks
    # ------------------------------------------------------------------

    async def fetch_banks(
        self, *, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return all banks, optionally filtered by website_status."""
        if status is not None:
            return await self.pool.fetch(
                "SELECT * FROM banks WHERE website_status = $1 ORDER BY bank_code",
                status,
            )
        return await self.pool.fetch("SELECT * FROM banks ORDER BY bank_code")

    async def upsert_bank(
        self,
        *,
        bank_code: str,
        bank_name: str,
        website_url: Optional[str] = None,
        bank_category: str,
        bank_type: str,
    ) -> dict[str, Any]:
        """Insert or update a bank by bank_code, returning the row."""
        return await self.pool.fetchrow(
            """
            INSERT INTO banks (bank_code, bank_name, website_url, bank_category, bank_type)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (bank_code)
            DO UPDATE SET
                bank_name = EXCLUDED.bank_name,
                website_url = EXCLUDED.website_url,
                bank_category = EXCLUDED.bank_category,
                bank_type = EXCLUDED.bank_type
            RETURNING *
            """,
            bank_code,
            bank_name,
            website_url,
            bank_category,
            bank_type,
        )

    async def update_bank_status(
        self,
        *,
        bank_id: str,
        website_status: str,
        last_crawled_at: Optional[str] = None,
        crawl_streak: Optional[int] = None,
    ) -> dict[str, Any]:
        """Update crawl-related status fields on a bank."""
        return await self.pool.fetchrow(
            """
            UPDATE banks
            SET website_status = $2,
                last_crawled_at = COALESCE($3::timestamptz, last_crawled_at),
                crawl_streak = COALESCE($4, crawl_streak)
            WHERE id = $1::uuid
            RETURNING *
            """,
            bank_id,
            website_status,
            last_crawled_at,
            crawl_streak,
        )

    # ------------------------------------------------------------------
    # Bank Strategies
    # ------------------------------------------------------------------

    async def fetch_active_strategies(
        self, *, bank_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return active primary strategies joined with bank info, optionally for a specific bank."""
        if bank_id is not None:
            return await self.pool.fetch(
                """
                SELECT bs.*, b.bank_code, b.bank_name
                FROM bank_strategies bs
                JOIN banks b ON b.id = bs.bank_id
                WHERE bs.is_active = true AND bs.is_primary = true AND bs.bank_id = $1::uuid
                ORDER BY bs.version DESC
                """,
                bank_id,
            )
        return await self.pool.fetch(
            """
            SELECT bs.*, b.bank_code, b.bank_name
            FROM bank_strategies bs
            JOIN banks b ON b.id = bs.bank_id
            WHERE bs.is_active = true AND bs.is_primary = true
            ORDER BY bs.bank_id, bs.version DESC
            """
        )

    async def upsert_strategy(
        self,
        *,
        bank_id: str,
        selectors: Optional[dict] = None,
        loan_page_urls: Optional[list] = None,
        anti_bot_detected: bool = False,
        anti_bot_type: Optional[str] = None,
        bypass_method: Optional[str] = None,
        rate_limit_ms: int = 2000,
        is_active: bool = True,
        is_primary: bool = True,
    ) -> dict[str, Any]:
        """Insert or update a primary active strategy with optimistic locking via version."""
        return await self.pool.fetchrow(
            """
            INSERT INTO bank_strategies (
                bank_id, selectors, loan_page_urls,
                anti_bot_detected, anti_bot_type, bypass_method,
                rate_limit_ms, is_active, is_primary, version
            )
            VALUES ($1::uuid, $2::jsonb, $3::jsonb, $4, $5, $6, $7, $8, $9, 1)
            ON CONFLICT (bank_id) WHERE (is_primary = true AND is_active = true)
            DO UPDATE SET
                selectors = EXCLUDED.selectors,
                loan_page_urls = EXCLUDED.loan_page_urls,
                anti_bot_detected = EXCLUDED.anti_bot_detected,
                anti_bot_type = EXCLUDED.anti_bot_type,
                bypass_method = EXCLUDED.bypass_method,
                rate_limit_ms = EXCLUDED.rate_limit_ms,
                version = bank_strategies.version + 1
            RETURNING *
            """,
            bank_id,
            json.dumps(selectors or {}),
            json.dumps(loan_page_urls or []),
            anti_bot_detected,
            anti_bot_type,
            bypass_method,
            rate_limit_ms,
            is_active,
            is_primary,
        )

    # ------------------------------------------------------------------
    # Crawl Logs
    # ------------------------------------------------------------------

    async def create_crawl_log(
        self,
        *,
        bank_id: str,
        strategy_id: Optional[str] = None,
        status: str = "queued",
    ) -> dict[str, Any]:
        """Create a new crawl log entry."""
        return await self.pool.fetchrow(
            """
            INSERT INTO crawl_logs (bank_id, strategy_id, status)
            VALUES ($1::uuid, $2::uuid, $3)
            RETURNING *
            """,
            bank_id,
            strategy_id,
            status,
        )

    async def update_crawl_log(
        self,
        *,
        crawl_log_id: str,
        status: str,
        programs_found: int = 0,
        programs_new: int = 0,
        programs_updated: int = 0,
        pages_crawled: int = 0,
        duration_ms: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stack: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update a crawl log with results."""
        return await self.pool.fetchrow(
            """
            UPDATE crawl_logs
            SET status = $2,
                programs_found = $3,
                programs_new = $4,
                programs_updated = $5,
                pages_crawled = $6,
                duration_ms = $7,
                error_type = $8,
                error_message = $9,
                error_stack = $10
            WHERE id = $1::uuid
            RETURNING *
            """,
            crawl_log_id,
            status,
            programs_found,
            programs_new,
            programs_updated,
            pages_crawled,
            duration_ms,
            error_type,
            error_message,
            error_stack,
        )

    async def update_strategy_success_rate(
        self, *, strategy_id: str
    ) -> None:
        """Recompute success_rate from crawl_logs for a single strategy.

        success_rate = successful crawls / total completed crawls (last 30 days).
        Only counts crawls that finished (status in 'success', 'failed').
        """
        await self.pool.execute(
            """
            UPDATE bank_strategies
            SET success_rate = COALESCE((
                SELECT
                    CASE WHEN COUNT(*) = 0 THEN 0.00
                    ELSE ROUND(
                        COUNT(*) FILTER (WHERE status = 'success')::numeric
                        / COUNT(*)::numeric, 2
                    )
                    END
                FROM crawl_logs
                WHERE strategy_id = $1::uuid
                    AND status IN ('success', 'failed')
                    AND created_at > NOW() - INTERVAL '30 days'
            ), 0.00)
            WHERE id = $1::uuid
            """,
            strategy_id,
        )

    async def update_crawl_log_programs(
        self, *, crawl_log_id: str, programs_found: int
    ) -> None:
        """Update only the programs_found count on a crawl log.

        Intentionally separate from update_crawl_log() to avoid overwriting
        crawler-owned fields (status, pages_crawled, duration_ms, etc.).
        The parser owns programs_found; the crawler owns everything else.
        """
        await self.pool.execute(
            "UPDATE crawl_logs SET programs_found = $2 WHERE id = $1::uuid",
            crawl_log_id,
            programs_found,
        )

    # ------------------------------------------------------------------
    # Crawl Raw Data
    # ------------------------------------------------------------------

    async def store_raw_html(
        self,
        *,
        crawl_log_id: str,
        bank_id: str,
        page_url: str,
        raw_html: str,
    ) -> dict[str, Any]:
        """Store raw HTML from a crawled page.

        Returns metadata only (not the raw_html blob) to avoid keeping
        multi-MB strings in Python memory after insertion.
        """
        return await self.pool.fetchrow(
            """
            INSERT INTO crawl_raw_data (crawl_log_id, bank_id, page_url, raw_html)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            RETURNING id, crawl_log_id, bank_id, page_url, parsed, created_at
            """,
            crawl_log_id,
            bank_id,
            page_url,
            raw_html,
        )

    async def fetch_unparsed_html(
        self, *, bank_id: Optional[str] = None, bank_code: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch unparsed row metadata (WITHOUT raw_html) for parsing.

        Returns rows with id, bank_id, bank_code, bank_name, page_url,
        crawl_log_id, selectors. Use fetch_raw_html_by_id() to load the
        actual HTML one row at a time during processing.
        """
        base_query = """
            SELECT
                crd.id,
                crd.crawl_log_id,
                crd.bank_id,
                crd.page_url,
                crd.created_at,
                b.bank_code,
                b.bank_name,
                bs.selectors
            FROM crawl_raw_data crd
            JOIN banks b ON b.id = crd.bank_id
            LEFT JOIN bank_strategies bs
                ON bs.bank_id = crd.bank_id
                AND bs.is_active = true
                AND bs.is_primary = true
            WHERE crd.parsed = false
        """
        if bank_id is not None:
            return await self.pool.fetch(
                base_query + " AND crd.bank_id = $1::uuid ORDER BY crd.created_at",
                bank_id,
            )
        if bank_code is not None:
            return await self.pool.fetch(
                base_query + " AND b.bank_code = $1 ORDER BY crd.created_at",
                bank_code,
            )
        return await self.pool.fetch(base_query + " ORDER BY crd.created_at")

    async def fetch_raw_html_by_id(self, *, raw_data_id: str) -> Optional[str]:
        """Fetch only the raw_html for a single crawl_raw_data row.

        Returns None if the row doesn't exist. Loads one HTML blob at a
        time to avoid holding hundreds of MB in memory simultaneously.
        """
        return await self.pool.fetchval(
            "SELECT raw_html FROM crawl_raw_data WHERE id = $1::uuid",
            raw_data_id,
        )

    async def mark_parsed(
        self, *, raw_data_id: str, programs_produced: int = 0
    ) -> None:
        """Mark a raw data row as parsed with the count of programs extracted."""
        try:
            await self.pool.execute(
                """
                UPDATE crawl_raw_data
                SET parsed = true, programs_produced = $2
                WHERE id = $1::uuid
                """,
                raw_data_id,
                programs_produced,
            )
        except asyncpg.UndefinedColumnError:
            logger.warning("mark_parsed: programs_produced column missing — using fallback query")
            await self.pool.execute(
                """
                UPDATE crawl_raw_data
                SET parsed = true
                WHERE id = $1::uuid
                """,
                raw_data_id,
            )

    # ------------------------------------------------------------------
    # Loan Programs
    # ------------------------------------------------------------------

    async def upsert_loan_program(
        self,
        *,
        bank_id: str,
        program_name: str,
        loan_type: str,
        rate_fixed: Optional[float] = None,
        rate_floating: Optional[float] = None,
        rate_promo: Optional[float] = None,
        rate_promo_duration_months: Optional[int] = None,
        min_interest_rate: Optional[float] = None,
        max_interest_rate: Optional[float] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        min_tenor_months: Optional[int] = None,
        max_tenor_months: Optional[int] = None,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        min_income: Optional[float] = None,
        employment_types: Optional[list] = None,
        required_documents: Optional[list] = None,
        admin_fee_pct: Optional[float] = None,
        provision_fee_pct: Optional[float] = None,
        insurance_required: Optional[bool] = None,
        features: Optional[list] = None,
        data_confidence: float = 0.0,
        completeness_score: float = 0.0,
        raw_data: Optional[dict] = None,
        source_url: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Insert a new loan program version, marking previous versions as not latest.

        Returns None if the row is rejected by data quality checks.
        """
        # A1: Minimum confidence threshold — reject garbage extractions
        if data_confidence < MIN_CONFIDENCE_THRESHOLD:
            logger.warning(
                "Skipping loan program '%s' for bank %s: "
                "data_confidence %.2f below threshold %.2f",
                program_name, bank_id, data_confidence, MIN_CONFIDENCE_THRESHOLD,
            )
            return None

        # A2: Rate sanity bounds — nullify out-of-range rates
        if min_interest_rate is not None and not (MIN_RATE_BOUND <= min_interest_rate <= MAX_RATE_BOUND):
            logger.warning(
                "Nullifying min_interest_rate %.2f for '%s' (bank %s): outside [%.1f, %.1f]",
                min_interest_rate, program_name, bank_id, MIN_RATE_BOUND, MAX_RATE_BOUND,
            )
            min_interest_rate = None
        if max_interest_rate is not None and not (MIN_RATE_BOUND <= max_interest_rate <= MAX_RATE_BOUND):
            logger.warning(
                "Nullifying max_interest_rate %.2f for '%s' (bank %s): outside [%.1f, %.1f]",
                max_interest_rate, program_name, bank_id, MIN_RATE_BOUND, MAX_RATE_BOUND,
            )
            max_interest_rate = None

        # A3: Min/max cross-validation — swap if inverted
        if (
            min_interest_rate is not None
            and max_interest_rate is not None
            and min_interest_rate > max_interest_rate
        ):
            logger.warning(
                "Swapping inverted interest rates (%.2f > %.2f) for '%s' (bank %s)",
                min_interest_rate, max_interest_rate, program_name, bank_id,
            )
            min_interest_rate, max_interest_rate = max_interest_rate, min_interest_rate

        if (
            min_amount is not None
            and max_amount is not None
            and min_amount > max_amount
        ):
            logger.warning(
                "Swapping inverted amounts (%.2f > %.2f) for '%s' (bank %s)",
                min_amount, max_amount, program_name, bank_id,
            )
            min_amount, max_amount = max_amount, min_amount

        if (
            min_tenor_months is not None
            and max_tenor_months is not None
            and min_tenor_months > max_tenor_months
        ):
            logger.warning(
                "Swapping inverted tenor months (%d > %d) for '%s' (bank %s)",
                min_tenor_months, max_tenor_months, program_name, bank_id,
            )
            min_tenor_months, max_tenor_months = max_tenor_months, min_tenor_months

        # Mark previous versions as not latest and insert new version atomically
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE loan_programs
                    SET is_latest = false
                    WHERE bank_id = $1::uuid
                      AND program_name = $2
                      AND loan_type = $3
                      AND is_latest = true
                    """,
                    bank_id,
                    program_name,
                    loan_type,
                )

                return await conn.fetchrow(
                    """
                    INSERT INTO loan_programs (
                        bank_id, program_name, loan_type,
                        rate_fixed, rate_floating, rate_promo, rate_promo_duration_months,
                        min_interest_rate, max_interest_rate,
                        min_amount, max_amount, min_tenor_months, max_tenor_months,
                        min_age, max_age, min_income,
                        employment_types, required_documents,
                        admin_fee_pct, provision_fee_pct, insurance_required,
                        features, data_confidence, completeness_score,
                        raw_data, source_url, is_latest
                    )
                    VALUES (
                        $1::uuid, $2, $3,
                        $4, $5, $6, $7,
                        $8, $9,
                        $10, $11, $12, $13,
                        $14, $15, $16,
                        $17::jsonb, $18::jsonb,
                        $19, $20, $21,
                        $22::jsonb, $23, $24,
                        $25::jsonb, $26, true
                    )
                    RETURNING *
                    """,
                    bank_id,
                    program_name,
                    loan_type,
                    rate_fixed,
                    rate_floating,
                    rate_promo,
                    rate_promo_duration_months,
                    min_interest_rate,
                    max_interest_rate,
                    min_amount,
                    max_amount,
                    min_tenor_months,
                    max_tenor_months,
                    min_age,
                    max_age,
                    min_income,
                    json.dumps(employment_types or []),
                    json.dumps(required_documents or []),
                    admin_fee_pct,
                    provision_fee_pct,
                    insurance_required,
                    json.dumps(features or []),
                    data_confidence,
                    completeness_score,
                    json.dumps(raw_data or {}),
                    source_url,
                )

    async def fetch_loan_programs(
        self,
        *,
        bank_id: Optional[str] = None,
        loan_type: Optional[str] = None,
        latest_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch loan programs with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []
        param_idx = 1

        if latest_only:
            conditions.append("is_latest = true")

        if bank_id is not None:
            conditions.append(f"bank_id = ${param_idx}::uuid")
            params.append(bank_id)
            param_idx += 1

        if loan_type is not None:
            conditions.append(f"loan_type = ${param_idx}")
            params.append(loan_type)
            param_idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM loan_programs {where} ORDER BY bank_id, program_name"

        return await self.pool.fetch(query, *params)

    # ------------------------------------------------------------------
    # Strategy Feedback
    # ------------------------------------------------------------------

    async def add_strategy_feedback(
        self,
        *,
        strategy_id: str,
        test_approach: str,
        result: str,
        improvement_score: Optional[float] = None,
        recommended_changes: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Record feedback for a strategy test."""
        return await self.pool.fetchrow(
            """
            INSERT INTO strategy_feedback (
                strategy_id, test_approach, result,
                improvement_score, recommended_changes
            )
            VALUES ($1::uuid, $2, $3, $4, $5::jsonb)
            RETURNING *
            """,
            strategy_id,
            test_approach,
            result,
            improvement_score,
            json.dumps(recommended_changes or {}),
        )

    # ------------------------------------------------------------------
    # Ringkas Recommendations
    # ------------------------------------------------------------------

    async def clear_recommendations_by_type(self, *, rec_type: str) -> int:
        """Delete existing recommendations of the given type.

        Returns the number of rows deleted.
        """
        result = await self.pool.execute(
            "DELETE FROM ringkas_recommendations WHERE rec_type = $1",
            rec_type,
        )
        # asyncpg execute returns 'DELETE N'
        return int(result.split()[-1])

    async def add_recommendation(
        self,
        *,
        rec_type: str,
        priority: int,
        title: str,
        summary: Optional[str] = None,
        impact_score: Optional[float] = None,
        suggested_actions: Optional[list] = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        """Add a Ringkas recommendation."""
        return await self.pool.fetchrow(
            """
            INSERT INTO ringkas_recommendations (
                rec_type, priority, title, summary,
                impact_score, suggested_actions, status
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING *
            """,
            rec_type,
            priority,
            title,
            summary,
            impact_score,
            json.dumps(suggested_actions or []),
            status,
        )

    # ------------------------------------------------------------------
    # Crawl Stats
    # ------------------------------------------------------------------

    async def get_crawl_stats(self, *, days: int = 7) -> dict[str, Any]:
        """Get aggregated crawl statistics for the last N days."""
        row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total_crawls,
                COUNT(DISTINCT bank_id) AS banks_crawled,
                COUNT(*) FILTER (WHERE status = 'success') AS successful,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE status = 'blocked') AS blocked,
                COUNT(*) FILTER (WHERE status = 'timeout') AS timed_out,
                COALESCE(SUM(programs_found), 0) AS total_programs_found,
                COALESCE(SUM(programs_new), 0) AS total_programs_new,
                COALESCE(AVG(duration_ms), 0)::integer AS avg_duration_ms
            FROM crawl_logs
            WHERE created_at >= NOW() - make_interval(days => $1)
            """,
            days,
        )
        return dict(row) if row else {}

    async def get_parse_stats(self, *, days: int = 7) -> list[dict[str, Any]]:
        """Get per-bank parse success metrics for the last N days.

        Returns rows with: bank_code, total_raw_rows, parsed_rows,
        rows_with_programs, total_programs_produced.
        """
        try:
            rows = await self.pool.fetch(
                """
                SELECT
                    b.bank_code,
                    COUNT(*) AS total_raw_rows,
                    COUNT(*) FILTER (WHERE crd.parsed = true) AS parsed_rows,
                    COUNT(*) FILTER (WHERE crd.programs_produced > 0)
                        AS rows_with_programs,
                    COALESCE(SUM(crd.programs_produced), 0)
                        AS total_programs_produced
                FROM crawl_raw_data crd
                JOIN banks b ON b.id = crd.bank_id
                WHERE crd.created_at >= NOW() - make_interval(days => $1)
                GROUP BY b.bank_code
                ORDER BY b.bank_code
                """,
                days,
            )
        except asyncpg.UndefinedColumnError:
            rows = await self.pool.fetch(
                """
                SELECT
                    b.bank_code,
                    COUNT(*) AS total_raw_rows,
                    COUNT(*) FILTER (WHERE crd.parsed = true) AS parsed_rows,
                    0 AS rows_with_programs,
                    0 AS total_programs_produced
                FROM crawl_raw_data crd
                JOIN banks b ON b.id = crd.bank_id
                WHERE crd.created_at >= NOW() - make_interval(days => $1)
                GROUP BY b.bank_code
                ORDER BY b.bank_code
                """,
                days,
            )
        return [dict(r) for r in rows]

    async def get_bank_crawl_stats(
        self, *, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get per-bank crawl success metrics for the last N days.

        Returns rows with: bank_code, total_crawls, successful,
        failed, blocked.
        """
        rows = await self.pool.fetch(
            """
            SELECT
                b.bank_code,
                COUNT(*) AS total_crawls,
                COUNT(*) FILTER (WHERE cl.status = 'success') AS successful,
                COUNT(*) FILTER (WHERE cl.status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE cl.status = 'blocked') AS blocked
            FROM crawl_logs cl
            JOIN banks b ON b.id = cl.bank_id
            WHERE cl.created_at >= NOW() - make_interval(days => $1)
            GROUP BY b.bank_code
            ORDER BY b.bank_code
            """,
            days,
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Agent Run Tracking
    # ------------------------------------------------------------------

    async def log_agent_start(
        self, *, agent_name: str, job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Insert a new agent_runs row with status='running'.

        Returns the row including the generated id for later updates.
        """
        row = await self.pool.fetchrow(
            """
            INSERT INTO agent_runs (agent_name, status, job_id)
            VALUES ($1, 'running', $2)
            RETURNING *
            """,
            agent_name,
            job_id,
        )
        return dict(row)

    async def log_agent_finish(
        self,
        *,
        run_id: str,
        result: dict,
        rows_written: int = 0,
    ) -> None:
        """Mark an agent run as successful."""
        await self.pool.execute(
            """
            UPDATE agent_runs
            SET status = 'success',
                finished_at = NOW(),
                result = $2::jsonb,
                rows_written = $3
            WHERE id = $1::uuid
            """,
            run_id,
            json.dumps(result),
            rows_written,
        )

    async def log_agent_error(
        self, *, run_id: str, error_message: str
    ) -> None:
        """Mark an agent run as failed with an error message."""
        await self.pool.execute(
            """
            UPDATE agent_runs
            SET status = 'failed',
                finished_at = NOW(),
                error_message = $2
            WHERE id = $1::uuid
            """,
            run_id,
            error_message,
        )

    async def get_latest_agent_runs(self) -> list[dict[str, Any]]:
        """Return the most recent run per agent_name."""
        rows = await self.pool.fetch(
            """
            SELECT DISTINCT ON (agent_name) *
            FROM agent_runs
            ORDER BY agent_name, started_at DESC
            """
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Dashboard Queries
    # ------------------------------------------------------------------

    async def get_dashboard_alerts(self) -> list[dict[str, Any]]:
        """Return aggregated alerts across 5 categories for the dashboard.

        Categories: crawl_failures, rate_anomalies, data_quality,
        stale_data, strategy_health.
        """
        alerts: list[dict[str, Any]] = []

        # 1a. Crawl failures — unreachable banks
        rows = await self.pool.fetch(
            """
            SELECT bank_code
            FROM banks
            WHERE website_status = 'unreachable'
              AND (last_crawled_at IS NULL
                   OR last_crawled_at < NOW() - INTERVAL '24 hours')
            ORDER BY bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "crawl_failures",
                "type": "unreachable",
                "message": f"{len(codes)} bank(s) unreachable for 24+ hours",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Re-crawl", "agent": "crawler"},
            })

        # 1b. Crawl failures — anti-bot blocks in last 24h
        rows = await self.pool.fetch(
            """
            SELECT DISTINCT b.bank_code
            FROM crawl_logs cl
            JOIN banks b ON b.id = cl.bank_id
            WHERE cl.status = 'blocked'
              AND cl.created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY b.bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "crawl_failures",
                "type": "anti_bot",
                "message": f"{len(codes)} bank(s) blocked by anti-bot in last 24h",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Review strategy", "agent": "strategist"},
            })

        # 2. Rate anomalies — current vs previous version delta > 0.5
        rows = await self.pool.fetch(
            """
            SELECT DISTINCT b.bank_code
            FROM loan_programs curr
            JOIN loan_programs prev
              ON prev.bank_id = curr.bank_id
             AND prev.loan_type = curr.loan_type
             AND prev.program_name = curr.program_name
             AND prev.is_latest = false
            JOIN banks b ON b.id = curr.bank_id
            WHERE curr.is_latest = true
              AND curr.min_interest_rate IS NOT NULL
              AND prev.min_interest_rate IS NOT NULL
              AND ABS(curr.min_interest_rate - prev.min_interest_rate) > 0.5
            ORDER BY b.bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "rate_anomalies",
                "type": "large_rate_change",
                "message": f"{len(codes)} bank(s) with interest rate change > 0.5%",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Review rates", "agent": "parser"},
            })

        # 3. Data quality — avg completeness_score < 0.5
        rows = await self.pool.fetch(
            """
            SELECT b.bank_code
            FROM loan_programs lp
            JOIN banks b ON b.id = lp.bank_id
            WHERE lp.is_latest = true
            GROUP BY b.bank_code
            HAVING AVG(lp.completeness_score) < 0.5
            ORDER BY b.bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "data_quality",
                "type": "low_completeness",
                "message": f"{len(codes)} bank(s) with avg completeness below 50%",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Re-parse", "agent": "parser"},
            })

        # 4. Stale data — active banks not crawled in 3+ days
        rows = await self.pool.fetch(
            """
            SELECT bank_code
            FROM banks
            WHERE website_status != 'unreachable'
              AND (last_crawled_at IS NULL
                   OR last_crawled_at < NOW() - INTERVAL '3 days')
            ORDER BY bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "stale_data",
                "type": "not_crawled_3d",
                "message": f"{len(codes)} active bank(s) not crawled in 3+ days",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Schedule crawl", "agent": "crawler"},
            })

        # 5. Strategy health — active strategies with success_rate < 0.3
        rows = await self.pool.fetch(
            """
            SELECT b.bank_code
            FROM bank_strategies bs
            JOIN banks b ON b.id = bs.bank_id
            WHERE bs.is_active = true
              AND bs.is_primary = true
              AND COALESCE(bs.success_rate, 0) < 0.3
            ORDER BY b.bank_code
            """
        )
        if rows:
            codes = [r["bank_code"] for r in rows]
            alerts.append({
                "category": "strategy_health",
                "type": "low_success_rate",
                "message": f"{len(codes)} bank(s) with strategy success rate below 30%",
                "count": len(codes),
                "bank_codes": codes,
                "cta": {"label": "Rebuild strategy", "agent": "strategist"},
            })

        return alerts

    async def get_dashboard_changes(self, date: str) -> list[dict[str, Any]]:
        """Return meaningful changes for a given date (YYYY-MM-DD).

        Covers: new programs, rate decreases, rate increases, bank status changes.
        """
        changes: list[dict[str, Any]] = []

        # New programs added on that date
        row = await self.pool.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_programs
            WHERE is_latest = true
              AND DATE(created_at) = $1::date
            """,
            date,
        )
        new_count = row["cnt"] if row else 0
        if new_count > 0:
            changes.append({
                "type": "new_programs",
                "count": int(new_count),
                "detail": f"{new_count} new loan program(s) added on {date}",
            })

        # Rate decreases — current min_interest_rate < previous version
        row = await self.pool.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_programs curr
            JOIN loan_programs prev
              ON prev.bank_id = curr.bank_id
             AND prev.loan_type = curr.loan_type
             AND prev.program_name = curr.program_name
             AND prev.is_latest = false
            WHERE curr.is_latest = true
              AND DATE(curr.updated_at) = $1::date
              AND curr.min_interest_rate IS NOT NULL
              AND prev.min_interest_rate IS NOT NULL
              AND curr.min_interest_rate < prev.min_interest_rate
            """,
            date,
        )
        decrease_count = row["cnt"] if row else 0
        if decrease_count > 0:
            changes.append({
                "type": "rate_decrease",
                "count": int(decrease_count),
                "detail": f"{decrease_count} program(s) had rate decreases on {date}",
            })

        # Rate increases — current min_interest_rate > previous version
        row = await self.pool.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM loan_programs curr
            JOIN loan_programs prev
              ON prev.bank_id = curr.bank_id
             AND prev.loan_type = curr.loan_type
             AND prev.program_name = curr.program_name
             AND prev.is_latest = false
            WHERE curr.is_latest = true
              AND DATE(curr.updated_at) = $1::date
              AND curr.min_interest_rate IS NOT NULL
              AND prev.min_interest_rate IS NOT NULL
              AND curr.min_interest_rate > prev.min_interest_rate
            """,
            date,
        )
        increase_count = row["cnt"] if row else 0
        if increase_count > 0:
            changes.append({
                "type": "rate_increase",
                "count": int(increase_count),
                "detail": f"{increase_count} program(s) had rate increases on {date}",
            })

        # Bank status changes — banks with updated_at on that date
        row = await self.pool.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM banks
            WHERE DATE(updated_at) = $1::date
            """,
            date,
        )
        status_count = row["cnt"] if row else 0
        if status_count > 0:
            changes.append({
                "type": "bank_status_change",
                "count": int(status_count),
                "detail": f"{status_count} bank(s) had status updates on {date}",
            })

        return changes

    async def get_dashboard_quality(self) -> dict[str, Any]:
        """Return data quality distribution across banks.

        Buckets: high (>0.8), medium (0.5-0.8), low (<0.5).
        """
        row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE avg_score > 0.8) AS high,
                COUNT(*) FILTER (WHERE avg_score BETWEEN 0.5 AND 0.8) AS medium,
                COUNT(*) FILTER (WHERE avg_score < 0.5) AS low,
                COALESCE(AVG(avg_score), 0.0) AS avg_completeness
            FROM (
                SELECT bank_id, AVG(completeness_score) AS avg_score
                FROM loan_programs
                WHERE is_latest = true
                GROUP BY bank_id
            ) sub
            """
        )
        if not row:
            return {
                "high": {"count": 0, "threshold": 0.8},
                "medium": {"count": 0, "threshold": 0.5},
                "low": {"count": 0, "threshold": 0.0},
                "avg_completeness": 0.0,
            }
        return {
            "high": {"count": int(row["high"]), "threshold": 0.8},
            "medium": {"count": int(row["medium"]), "threshold": 0.5},
            "low": {"count": int(row["low"]), "threshold": 0.0},
            "avg_completeness": float(row["avg_completeness"]),
        }

    async def get_crawl_analytics(self, *, days: int = 7) -> dict[str, Any]:
        """Return extended crawl analytics for the dashboard.

        Includes: summary stats (with prev-week comparison), error breakdown,
        and daily success rates over days*4 window for trend charts.
        """
        # Current window stats
        stats_row = await self.pool.fetchrow(
            """
            SELECT
                COUNT(*) AS total_crawls,
                CASE WHEN COUNT(*) = 0 THEN 0.0
                     ELSE ROUND(
                         COUNT(*) FILTER (WHERE status = 'success')::numeric
                         / COUNT(*)::numeric, 4
                     )
                END AS success_rate,
                COALESCE(AVG(duration_ms), 0.0) AS avg_duration_ms,
                COALESCE(SUM(programs_found), 0) AS programs_found,
                COALESCE(SUM(programs_new), 0) AS programs_new
            FROM crawl_logs
            WHERE created_at >= NOW() - make_interval(days => $1)
            """,
            days,
        )

        # Previous window stats (for comparison)
        prev_row = await self.pool.fetchrow(
            """
            SELECT
                CASE WHEN COUNT(*) = 0 THEN 0.0
                     ELSE ROUND(
                         COUNT(*) FILTER (WHERE status = 'success')::numeric
                         / COUNT(*)::numeric, 4
                     )
                END AS success_rate_prev_week
            FROM crawl_logs
            WHERE created_at >= NOW() - make_interval(days => $1 * 2)
              AND created_at < NOW() - make_interval(days => $1)
            """,
            days,
        )

        # Error breakdown
        breakdown_rows = await self.pool.fetch(
            """
            SELECT status, COUNT(*) AS cnt
            FROM crawl_logs
            WHERE created_at >= NOW() - make_interval(days => $1)
            GROUP BY status
            """,
            days,
        )
        error_breakdown: dict[str, int] = {
            "success": 0,
            "failed": 0,
            "blocked": 0,
            "timeout": 0,
        }
        for r in breakdown_rows:
            key = r["status"]
            if key in error_breakdown:
                error_breakdown[key] = int(r["cnt"])

        # Daily success rate over expanded window
        daily_rows = await self.pool.fetch(
            """
            SELECT
                DATE(created_at) AS day,
                CASE WHEN COUNT(*) = 0 THEN 0.0
                     ELSE ROUND(
                         COUNT(*) FILTER (WHERE status = 'success')::numeric
                         / COUNT(*)::numeric, 4
                     )
                END AS rate
            FROM crawl_logs
            WHERE created_at >= NOW() - make_interval(days => $1 * 4)
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """,
            days,
        )
        daily_success_rate = [
            {"date": str(r["day"]), "rate": float(r["rate"])}
            for r in daily_rows
        ]

        return {
            "stats": {
                "total_crawls_7d": int(stats_row["total_crawls"]) if stats_row else 0,
                "success_rate": float(stats_row["success_rate"]) if stats_row else 0.0,
                "success_rate_prev_week": float(prev_row["success_rate_prev_week"]) if prev_row else 0.0,
                "avg_duration_ms": float(stats_row["avg_duration_ms"]) if stats_row else 0.0,
                "programs_found": int(stats_row["programs_found"]) if stats_row else 0,
                "programs_new": int(stats_row["programs_new"]) if stats_row else 0,
            },
            "error_breakdown": error_breakdown,
            "daily_success_rate": daily_success_rate,
        }

    async def get_loan_compare(self, loan_type: str) -> list[dict[str, Any]]:
        """Return latest loan programs for a given loan_type, ordered by min rate.

        Intended for side-by-side comparison across banks.
        """
        rows = await self.pool.fetch(
            """
            SELECT
                b.bank_code,
                b.bank_name,
                lp.min_interest_rate,
                lp.max_interest_rate,
                lp.rate_fixed,
                lp.rate_floating,
                lp.rate_promo,
                lp.rate_promo_duration_months,
                lp.completeness_score
            FROM loan_programs lp
            JOIN banks b ON lp.bank_id = b.id
            WHERE lp.is_latest = true
              AND lp.loan_type = $1
            ORDER BY lp.min_interest_rate ASC NULLS LAST
            """,
            loan_type,
        )
        return [dict(r) for r in rows]

    async def get_dashboard_sparklines(self, *, days: int = 7) -> dict[str, Any]:
        """Return 7-day sparkline data for KPI cards.

        Returns daily series for: bank count, program count,
        avg KPR rate, and avg completeness.
        """
        # Generate the date series to ensure no gaps
        date_series_sql = (
            "SELECT generate_series("
            "    (NOW() - make_interval(days => $1 - 1))::date,"
            "    NOW()::date,"
            "    '1 day'::interval"
            ")::date AS day"
        )

        # Cumulative bank count per day
        bank_rows = await self.pool.fetch(
            f"""
            WITH days AS ({date_series_sql})
            SELECT
                d.day,
                COUNT(b.id) AS cnt
            FROM days d
            LEFT JOIN banks b ON b.created_at::date <= d.day
            GROUP BY d.day
            ORDER BY d.day ASC
            """,
            days,
        )

        # Latest program count per day (programs created up to each day)
        program_rows = await self.pool.fetch(
            f"""
            WITH days AS ({date_series_sql})
            SELECT
                d.day,
                COUNT(lp.id) AS cnt
            FROM days d
            LEFT JOIN loan_programs lp
                ON lp.is_latest = true
               AND lp.created_at::date <= d.day
            GROUP BY d.day
            ORDER BY d.day ASC
            """,
            days,
        )

        # Avg KPR rate per day
        kpr_rows = await self.pool.fetch(
            f"""
            WITH days AS ({date_series_sql})
            SELECT
                d.day,
                COALESCE(AVG(lp.min_interest_rate), 0.0) AS avg_rate
            FROM days d
            LEFT JOIN loan_programs lp
                ON lp.is_latest = true
               AND lp.loan_type = 'KPR'
               AND lp.min_interest_rate IS NOT NULL
               AND lp.created_at::date <= d.day
            GROUP BY d.day
            ORDER BY d.day ASC
            """,
            days,
        )

        # Avg completeness per day
        quality_rows = await self.pool.fetch(
            f"""
            WITH days AS ({date_series_sql})
            SELECT
                d.day,
                COALESCE(AVG(lp.completeness_score), 0.0) AS avg_quality
            FROM days d
            LEFT JOIN loan_programs lp
                ON lp.is_latest = true
               AND lp.created_at::date <= d.day
            GROUP BY d.day
            ORDER BY d.day ASC
            """,
            days,
        )

        return {
            "banks": [int(r["cnt"]) for r in bank_rows],
            "programs": [int(r["cnt"]) for r in program_rows],
            "kpr_rate": [round(float(r["avg_rate"]), 2) for r in kpr_rows],
            "quality": [round(float(r["avg_quality"]), 4) for r in quality_rows],
        }

    async def update_recommendation(
        self,
        rec_id: Any,
        *,
        status: Optional[str] = None,
        status_note: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Update status and/or status_note on a recommendation. Returns updated row or None."""
        updates: list[str] = []
        params: list = []
        idx = 1
        if status is not None:
            updates.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if status_note is not None:
            updates.append(f"status_note = ${idx}")
            params.append(status_note)
            idx += 1
        if not updates:
            return None
        updates.append("updated_at = NOW()")
        params.append(rec_id)
        query = (
            f"UPDATE ringkas_recommendations SET {', '.join(updates)} "
            f"WHERE id = ${idx} RETURNING *"
        )
        row = await self.pool.fetchrow(query, *params)
        return dict(row) if row else None

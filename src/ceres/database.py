"""Async database module for CERES using asyncpg."""

from __future__ import annotations

import json
from typing import Any, Optional

import asyncpg


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
            statement_cache_size=0,
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
        """Store raw HTML from a crawled page."""
        return await self.pool.fetchrow(
            """
            INSERT INTO crawl_raw_data (crawl_log_id, bank_id, page_url, raw_html)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            RETURNING *
            """,
            crawl_log_id,
            bank_id,
            page_url,
            raw_html,
        )

    async def fetch_unparsed_html(
        self, *, bank_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch unparsed HTML rows joined with bank info and strategy selectors."""
        if bank_id is not None:
            return await self.pool.fetch(
                """
                SELECT
                    crd.*,
                    b.bank_code,
                    b.bank_name,
                    bs.selectors
                FROM crawl_raw_data crd
                JOIN banks b ON b.id = crd.bank_id
                LEFT JOIN bank_strategies bs
                    ON bs.bank_id = crd.bank_id
                    AND bs.is_active = true
                    AND bs.is_primary = true
                WHERE crd.parsed = false AND crd.bank_id = $1::uuid
                ORDER BY crd.created_at
                """,
                bank_id,
            )
        return await self.pool.fetch(
            """
            SELECT
                crd.*,
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
            ORDER BY crd.created_at
            """
        )

    async def mark_parsed(self, *, raw_data_id: str) -> None:
        """Mark a raw data row as parsed."""
        await self.pool.execute(
            "UPDATE crawl_raw_data SET parsed = true WHERE id = $1::uuid",
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
    ) -> dict[str, Any]:
        """Insert a new loan program version, marking previous versions as not latest."""
        # Mark previous versions as not latest
        await self.pool.execute(
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

        return await self.pool.fetchrow(
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

    # ------------------------------------------------------------------
    # Agent Run Tracking
    # ------------------------------------------------------------------

    async def log_agent_start(self, *, agent_name: str) -> dict[str, Any]:
        """Insert a new agent_runs row with status='running'.

        Returns the row including the generated id for later updates.
        """
        row = await self.pool.fetchrow(
            """
            INSERT INTO agent_runs (agent_name, status)
            VALUES ($1, 'running')
            RETURNING *
            """,
            agent_name,
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

"""Tests for the /api/rates/heatmap and /api/rates/trend endpoints."""

from __future__ import annotations

import inspect
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ceres.api.routes import router
from ceres.database import Database


def _make_test_app(mock_db: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app wired to the given mock database."""
    app = FastAPI()
    app.state.db = mock_db
    runner = MagicMock()
    runner.get_current_job.return_value = None
    app.state.task_runner = runner
    app.include_router(router, prefix="/api")
    return app


# ------------------------------------------------------------------
# GET /api/rates/heatmap
# ------------------------------------------------------------------


class TestRatesHeatmap:
    @pytest.mark.asyncio
    async def test_heatmap_returns_banks(self):
        """Multiple rows are pivoted into banks with rates dict keyed by loan_type."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[
            {"bank_id": "uuid-bca", "bank_code": "BCA", "bank_name": "Bank Central Asia",
             "website_status": "active", "loan_type": "KPR", "min_rate": 7.2},
            {"bank_id": "uuid-bca", "bank_code": "BCA", "bank_name": "Bank Central Asia",
             "website_status": "active", "loan_type": "KPA", "min_rate": 8.5},
            {"bank_id": "uuid-bri", "bank_code": "BRI", "bank_name": "Bank Rakyat Indonesia",
             "website_status": "active", "loan_type": "KPR", "min_rate": 6.9},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/heatmap")

        assert resp.status_code == 200
        data = resp.json()
        assert "banks" in data
        assert len(data["banks"]) == 2

        bca = data["banks"][0]
        assert bca["bank_code"] == "BCA"
        assert bca["bank_name"] == "Bank Central Asia"
        assert bca["website_status"] == "active"
        assert bca["rates"]["KPR"] == 7.2
        assert bca["rates"]["KPA"] == 8.5

        bri = data["banks"][1]
        assert bri["bank_code"] == "BRI"
        assert bri["rates"]["KPR"] == 6.9

    @pytest.mark.asyncio
    async def test_heatmap_empty_database(self):
        """No rows yields an empty banks list."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/heatmap")

        assert resp.status_code == 200
        assert resp.json() == {"banks": []}

    @pytest.mark.asyncio
    async def test_heatmap_bank_with_no_programs(self):
        """Bank row with NULL loan_type / min_rate results in an empty rates dict."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[
            {"bank_id": "uuid-mega", "bank_code": "MEGA", "bank_name": "Bank Mega",
             "website_status": "blocked", "loan_type": None, "min_rate": None},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/heatmap")

        assert resp.status_code == 200
        banks = resp.json()["banks"]
        assert len(banks) == 1
        assert banks[0]["bank_code"] == "MEGA"
        assert banks[0]["rates"] == {}


# ------------------------------------------------------------------
# GET /api/rates/trend
# ------------------------------------------------------------------


class TestRatesTrend:
    @pytest.mark.asyncio
    async def test_trend_happy_path(self):
        """Seven date/rate rows are returned as a series list."""
        db = AsyncMock()
        db.pool = AsyncMock()
        sample_rows = [
            {"date": date(2026, 3, 25 + i), "avg_min_rate": 7.0 + i * 0.1}
            for i in range(7)
        ]
        db.pool.fetch = AsyncMock(return_value=sample_rows)

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/trend")

        assert resp.status_code == 200
        data = resp.json()
        assert data["loan_type"] == "KPR"
        assert len(data["series"]) == 7
        assert data["series"][0]["date"] == "2026-03-25"
        assert data["series"][0]["avg_min_rate"] == 7.0
        assert data["series"][6]["date"] == "2026-03-31"

    @pytest.mark.asyncio
    async def test_trend_empty_data(self):
        """No matching rows returns the loan_type with an empty series."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/trend")

        assert resp.status_code == 200
        data = resp.json()
        assert data == {"loan_type": "KPR", "series": []}

    @pytest.mark.asyncio
    async def test_trend_custom_params(self):
        """Custom loan_type and days are forwarded to the database query."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/rates/trend?loan_type=MULTIGUNA&days=14")

        assert resp.status_code == 200
        assert resp.json()["loan_type"] == "MULTIGUNA"

        # Verify the DB was called with the correct positional args
        call_args = db.pool.fetch.call_args
        positional = call_args.args
        assert positional[1] == "MULTIGUNA"  # loan_type param
        assert positional[2] == 14  # days param


# ------------------------------------------------------------------
# Parser upsert signature
# ------------------------------------------------------------------


class TestUpsertLoanProgram:
    def test_upsert_accepts_min_max_rates(self):
        """upsert_loan_program() signature includes min/max_interest_rate kwargs."""
        sig = inspect.signature(Database.upsert_loan_program)
        params = sig.parameters

        assert "min_interest_rate" in params, (
            "upsert_loan_program must accept min_interest_rate keyword arg"
        )
        assert "max_interest_rate" in params, (
            "upsert_loan_program must accept max_interest_rate keyword arg"
        )

        # Both should be keyword-only with None defaults
        min_param = params["min_interest_rate"]
        max_param = params["max_interest_rate"]
        assert min_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert max_param.kind == inspect.Parameter.KEYWORD_ONLY
        assert min_param.default is None
        assert max_param.default is None

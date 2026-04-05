"""Tests for multi-value filter parameters across all paginated API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ceres.api.routes import router


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
# Loan Programs – multi-value loan_type
# ------------------------------------------------------------------


class TestLoanProgramsMultiValueLoanType:
    @pytest.mark.asyncio
    async def test_multi_loan_type_filters_matching_types(self):
        """?loan_type=KPR,KPA builds an ANY() filter and returns only matching types."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=2)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "p1", "loan_type": "KPR", "bank_code": "BCA", "program_name": "KPR BCA"},
            {"id": "p2", "loan_type": "KPA", "bank_code": "BCA", "program_name": "KPA BCA"},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs?loan_type=KPR,KPA")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

        # Verify the query used ANY() with the two values
        fetch_call = db.pool.fetch.call_args
        query_str = fetch_call.args[0]
        assert "ANY(" in query_str
        # The multi-value list should be passed as a parameter
        assert ["KPR", "KPA"] in list(fetch_call.args[1:])

    @pytest.mark.asyncio
    async def test_single_loan_type_backwards_compat(self):
        """?loan_type=KPR uses a simple = $N filter (no ANY)."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=1)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "p1", "loan_type": "KPR", "bank_code": "BCA", "program_name": "KPR BCA"},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs?loan_type=KPR")

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        # Single value should use = $N, not ANY()
        fetch_call = db.pool.fetch.call_args
        query_str = fetch_call.args[0]
        assert "ANY(" not in query_str
        assert "KPR" in fetch_call.args[1:]


# ------------------------------------------------------------------
# Loan Programs – rate range
# ------------------------------------------------------------------


class TestLoanProgramsRateRange:
    @pytest.mark.asyncio
    async def test_rate_range_filters_by_interest_rate(self):
        """?rate_min=5&rate_max=10 adds >= and <= conditions on rate columns."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=3)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "p1", "min_interest_rate": 5.5, "max_interest_rate": 8.0,
             "bank_code": "BCA", "loan_type": "KPR", "program_name": "KPR BCA"},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs?rate_min=5&rate_max=10")

        assert resp.status_code == 200

        # Both rate params should appear in the query
        fetch_call = db.pool.fetch.call_args
        query_str = fetch_call.args[0]
        assert "min_interest_rate >=" in query_str
        assert "max_interest_rate <=" in query_str
        # Verify the numeric values are passed
        positional = fetch_call.args[1:]
        assert 5.0 in positional
        assert 10.0 in positional

    @pytest.mark.asyncio
    async def test_rate_min_greater_than_rate_max_returns_400(self):
        """?rate_min=15&rate_max=5 is invalid and must return 400."""
        db = AsyncMock()
        db.pool = AsyncMock()

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs?rate_min=15&rate_max=5")

        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
        assert "rate_min" in body["error"].lower() or "INVALID_RATE_RANGE" == body.get("code")


# ------------------------------------------------------------------
# Crawl Logs – multi-value status
# ------------------------------------------------------------------


class TestCrawlLogsMultiValueStatus:
    @pytest.mark.asyncio
    async def test_multi_status_returns_both(self):
        """?status=failed,blocked uses ANY() to match both statuses."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=2)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "cl1", "status": "failed", "bank_code": "BCA", "created_at": "2026-04-01T00:00:00Z"},
            {"id": "cl2", "status": "blocked", "bank_code": "BRI", "created_at": "2026-04-01T01:00:00Z"},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/crawl-logs?status=failed,blocked")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

        # Verify the query used ANY() for multi-value status
        fetch_call = db.pool.fetch.call_args
        query_str = fetch_call.args[0]
        assert "ANY(" in query_str
        assert ["failed", "blocked"] in list(fetch_call.args[1:])


# ------------------------------------------------------------------
# Banks – multi-value category
# ------------------------------------------------------------------


class TestBanksMultiValueCategory:
    @pytest.mark.asyncio
    async def test_multi_category_returns_both(self):
        """?category=BUMN,BPD uses ANY() to match both categories."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=5)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "b1", "bank_code": "BRI", "bank_category": "BUMN", "programs_count": 2},
            {"id": "b2", "bank_code": "BJB", "bank_category": "BPD", "programs_count": 1},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks?category=BUMN,BPD")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["data"]) == 2

        # Verify the count query used ANY() for multi-value category
        fetchval_call = db.pool.fetchval.call_args
        count_query = fetchval_call.args[0]
        assert "ANY(" in count_query
        assert ["BUMN", "BPD"] in list(fetchval_call.args[1:])

    @pytest.mark.asyncio
    async def test_website_status_filter(self):
        """?website_status=active filters banks by their website status."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=30)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "b1", "bank_code": "BCA", "website_status": "active", "programs_count": 3},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks?website_status=active")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

        # Verify the query includes a website_status condition
        fetchval_call = db.pool.fetchval.call_args
        count_query = fetchval_call.args[0]
        assert "website_status" in count_query
        assert "active" in fetchval_call.args[1:]


# ------------------------------------------------------------------
# Strategies – pagination and filters
# ------------------------------------------------------------------


class TestStrategiesPagination:
    @pytest.mark.asyncio
    async def test_paginated_envelope(self):
        """Strategies endpoint returns paginated envelope with page/limit/total."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=45)
        db.pool.fetch = AsyncMock(side_effect=[
            [{"id": "s1", "bank_id": "00000000-0000-0000-0000-000000000001",
              "bank_code": "BCA", "bank_name": "Bank Central Asia",
              "success_rate": 0.85, "is_active": True}],
            [],  # trend query returns empty
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/strategies?page=2&limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 45
        assert data["page"] == 2
        assert data["limit"] == 10
        assert "data" in data


class TestStrategiesBankIdFilter:
    @pytest.mark.asyncio
    async def test_multi_bank_id_filter(self):
        """?bank_id=uuid1,uuid2 uses ANY() to match both bank IDs."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=2)
        db.pool.fetch = AsyncMock(side_effect=[
            [{"id": "s1", "bank_id": "uuid1", "bank_code": "BCA", "bank_name": "BCA",
              "success_rate": 0.9, "is_active": True},
             {"id": "s2", "bank_id": "uuid2", "bank_code": "BRI", "bank_name": "BRI",
              "success_rate": 0.7, "is_active": True}],
            [],  # trend query
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/strategies?bank_id=uuid1,uuid2")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["data"]) == 2

        # Verify ANY() was used for multi-bank filter (first fetch call is the main query)
        fetch_call = db.pool.fetch.call_args_list[0]
        query_str = fetch_call.args[0]
        assert "ANY(" in query_str
        assert sorted(fetch_call.args[1]) == ["uuid1", "uuid2"]


class TestStrategiesSuccessRateFilter:
    @pytest.mark.asyncio
    async def test_success_rate_min_filter(self):
        """?success_rate_min=50 filters strategies with success_rate >= 50."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=10)
        db.pool.fetch = AsyncMock(side_effect=[
            [{"id": "s1", "bank_id": "00000000-0000-0000-0000-000000000001",
              "bank_code": "BCA", "bank_name": "BCA",
              "success_rate": 0.85, "is_active": True}],
            [],  # trend query
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/strategies?success_rate_min=50")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

        # Verify success_rate >= condition is in the query (first fetch call is the main query)
        fetch_call = db.pool.fetch.call_args_list[0]
        query_str = fetch_call.args[0]
        assert "success_rate >=" in query_str
        assert 50.0 in fetch_call.args[1:]


# ------------------------------------------------------------------
# Empty multi-value param
# ------------------------------------------------------------------


class TestEmptyMultiValueParam:
    @pytest.mark.asyncio
    async def test_empty_loan_type_treated_as_no_filter(self):
        """?loan_type= (empty string) should return all programs, no type filter applied."""
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=100)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "p1", "loan_type": "KPR", "bank_code": "BCA", "program_name": "KPR BCA"},
            {"id": "p2", "loan_type": "MULTIGUNA", "bank_code": "BRI", "program_name": "MG BRI"},
        ])

        app = _make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs?loan_type=")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 100

        # With an empty loan_type, the query should NOT contain a loan_type filter
        fetch_call = db.pool.fetch.call_args
        query_str = fetch_call.args[0]
        assert "loan_type" not in query_str or "ANY(" not in query_str

import pytest
from unittest.mock import AsyncMock, MagicMock

from ceres.api.routes import router
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


def make_test_app(mock_db, mock_runner=None):
    app = FastAPI()
    app.state.db = mock_db
    if mock_runner is None:
        mock_runner = MagicMock()
        mock_runner.get_current_job.return_value = None
    app.state.task_runner = mock_runner
    app.include_router(router, prefix="/api")
    return app


class TestDashboardRoute:
    @pytest.mark.asyncio
    async def test_dashboard_overview(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "website_status": "active"},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successes": 8, "failures": 2,
            "blocked": 0, "banks_crawled": 1, "total_programs_found": 5,
        })
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_banks" in data
        assert "total_programs" in data
        assert "success_rate" in data
        assert data["success_rate"] == 0.8


class TestBanksRoute:
    @pytest.mark.asyncio
    async def test_list_banks_paginated(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=58)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "bank_name": "Bank Central Asia",
             "bank_category": "SWASTA_NASIONAL", "website_status": "active",
             "programs_count": 3}
        ])
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert data["total"] == 58

    @pytest.mark.asyncio
    async def test_get_bank_detail(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchrow = AsyncMock(return_value={"id": "1", "bank_code": "BCA", "bank_name": "BCA"})
        db.pool.fetch = AsyncMock(return_value=[])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks/1")
        assert resp.status_code == 200
        assert resp.json()["bank"]["bank_code"] == "BCA"

    @pytest.mark.asyncio
    async def test_get_bank_not_found(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchrow = AsyncMock(return_value=None)
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks/nonexistent")
        assert resp.status_code == 404


class TestCrawlLogsRoute:
    @pytest.mark.asyncio
    async def test_list_crawl_logs(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=0)
        db.pool.fetch = AsyncMock(return_value=[])
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/crawl-logs")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestLoanProgramsRoute:
    @pytest.mark.asyncio
    async def test_list_loan_programs(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=0)
        db.pool.fetch = AsyncMock(return_value=[])
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/loan-programs")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestCrawlTriggerRoutes:
    @pytest.mark.asyncio
    async def test_trigger_daily_crawl(self):
        db = AsyncMock()
        runner = AsyncMock()
        runner.get_current_job.return_value = None
        runner.start_job = AsyncMock(return_value=MagicMock(
            job_id="job-123", agent="daily", status="running",
            started_at="2026-04-01T00:00:00Z",
        ))
        app = make_test_app(db, runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawl/daily")
        assert resp.status_code == 202
        assert resp.json()["job_id"] == "job-123"

    @pytest.mark.asyncio
    async def test_trigger_returns_409_when_busy(self):
        db = AsyncMock()
        runner = AsyncMock()
        runner.get_current_job.return_value = None
        runner.start_job = AsyncMock(return_value=None)
        app = make_test_app(db, runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawl/daily")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_trigger_crawler_with_bank(self):
        db = AsyncMock()
        runner = AsyncMock()
        runner.get_current_job.return_value = None
        runner.start_job = AsyncMock(return_value=MagicMock(
            job_id="job-456", agent="crawler", status="running",
            started_at="2026-04-01T00:00:00Z",
        ))
        app = make_test_app(db, runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawl/crawler?bank=BCA")
        assert resp.status_code == 202
        runner.start_job.assert_called_once_with("crawler", bank_code="BCA")

    @pytest.mark.asyncio
    async def test_trigger_unknown_agent(self):
        db = AsyncMock()
        runner = AsyncMock()
        app = make_test_app(db, runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawl/unknown_agent")
        assert resp.status_code == 400

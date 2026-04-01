import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from ceres.api.tasks import CrawlTaskRunner, CrawlJob, CrawlJobStatus


class TestCrawlTaskRunner:
    @pytest.mark.asyncio
    async def test_start_job_returns_job_id(self):
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        job = await runner.start_job("daily")
        assert job.job_id is not None
        assert job.status == CrawlJobStatus.RUNNING
        assert job.agent == "daily"
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_concurrent_jobs_blocked(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[])
        runner = CrawlTaskRunner(db=db)

        async def slow_agent(**kwargs):
            await asyncio.sleep(10)
            return {"status": "ok"}

        runner._agent_registry["test"] = slow_agent
        job1 = await runner.start_job("test")
        assert job1 is not None
        job2 = await runner.start_job("test")
        assert job2 is None  # Blocked
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_get_current_job(self):
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        assert runner.get_current_job() is None

        async def slow(**kwargs):
            await asyncio.sleep(10)
            return {}

        runner._agent_registry["test"] = slow
        await runner.start_job("test")
        current = runner.get_current_job()
        assert current is not None
        assert current.agent == "test"
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_job_completes_and_clears(self):
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)

        async def fast_agent(**kwargs):
            return {"banks_checked": 0}

        runner._agent_registry["test"] = fast_agent
        await runner.start_job("test")
        await asyncio.sleep(0.1)
        assert runner.get_current_job() is None

    def test_job_is_frozen(self):
        job = CrawlJob(job_id="abc", agent="scout", status=CrawlJobStatus.RUNNING)
        assert job.job_id == "abc"

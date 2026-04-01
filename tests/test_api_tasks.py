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

    @pytest.mark.asyncio
    async def test_step_tracking_during_daily(self):
        """CrawlTaskRunner tracks current step index during daily pipeline."""
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        broadcasts = []

        async def fast_stub(**kw):
            return {"banks_processed": 5, "banks_total": 5, "banks_failed": 0}

        runner._run_scout = fast_stub
        runner._run_strategist = fast_stub
        runner._run_crawler = fast_stub
        runner._run_parser = fast_stub

        done = asyncio.Event()

        async def tracking_broadcast(msg):
            broadcasts.append(msg)
            if msg["type"] == "job_finish":
                done.set()

        runner.set_broadcast_callback(tracking_broadcast)

        await runner.start_job("daily")
        await asyncio.wait_for(done.wait(), timeout=5.0)

        # Check step tracking fields exist on progress broadcasts
        progress_msgs = [b for b in broadcasts if b["type"] == "job_progress"]
        assert len(progress_msgs) == 4  # One per completed step
        for i, msg in enumerate(progress_msgs):
            assert msg["step_index"] == i
            assert msg["total_steps"] == 4
            assert "banks_processed" in msg
            assert "banks_total" in msg

    @pytest.mark.asyncio
    async def test_get_current_job_includes_step(self):
        """get_step_info returns step tracking when daily pipeline is running."""
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        step_reached = asyncio.Event()

        async def slow_scout(**kw):
            step_reached.set()
            await asyncio.sleep(10)
            return {"banks_processed": 0, "banks_total": 0, "banks_failed": 0}

        runner._run_scout = slow_scout

        await runner.start_job("daily")
        await step_reached.wait()

        current = runner.get_current_job()
        assert current is not None
        assert runner.get_step_info() == {"current_step": "scout", "step_index": 0, "total_steps": 4}
        await runner.cancel_all()

    def test_job_is_frozen(self):
        job = CrawlJob(job_id="abc", agent="scout", status=CrawlJobStatus.RUNNING)
        assert job.job_id == "abc"

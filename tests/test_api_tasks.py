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
        runner._run_learning = fast_stub

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
        assert len(progress_msgs) == 5  # One per completed step (including learning)
        for i, msg in enumerate(progress_msgs):
            assert msg["step_index"] == i
            assert msg["total_steps"] == 5
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
        assert runner.get_step_info() == {"current_step": "scout", "step_index": 0, "total_steps": 5}
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_execute_logs_agent_start_and_finish(self):
        """_execute() calls log_agent_start before and log_agent_finish after the agent runs."""
        db = AsyncMock()
        db.log_agent_start = AsyncMock(return_value={"id": "run-123"})
        db.log_agent_finish = AsyncMock()
        db.log_agent_error = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        done = asyncio.Event()

        async def fast_agent(**kw):
            return {"result": "ok"}

        runner._agent_registry["test"] = fast_agent

        async def on_broadcast(msg):
            if msg["type"] == "job_finish":
                done.set()

        runner.set_broadcast_callback(on_broadcast)
        await runner.start_job("test")
        await asyncio.wait_for(done.wait(), timeout=5.0)

        db.log_agent_start.assert_called_once_with(agent_name="test")
        db.log_agent_finish.assert_called_once()
        finish_kwargs = db.log_agent_finish.call_args.kwargs
        assert finish_kwargs["run_id"] == "run-123"
        assert finish_kwargs["result"] == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_execute_logs_agent_error_on_failure(self):
        """_execute() calls log_agent_error when the agent throws."""
        db = AsyncMock()
        db.log_agent_start = AsyncMock(return_value={"id": "run-456"})
        db.log_agent_finish = AsyncMock()
        db.log_agent_error = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        done = asyncio.Event()

        async def failing_agent(**kw):
            raise RuntimeError("bank timeout")

        runner._agent_registry["test"] = failing_agent

        async def on_broadcast(msg):
            if msg["type"] == "job_error":
                done.set()

        runner.set_broadcast_callback(on_broadcast)
        await runner.start_job("test")
        await asyncio.wait_for(done.wait(), timeout=5.0)

        db.log_agent_start.assert_called_once_with(agent_name="test")
        db.log_agent_error.assert_called_once()
        error_kwargs = db.log_agent_error.call_args.kwargs
        assert error_kwargs["run_id"] == "run-456"
        assert "bank timeout" in error_kwargs["error_message"]
        db.log_agent_finish.assert_not_called()

    @pytest.mark.asyncio
    async def test_logging_failure_does_not_crash_agent(self):
        """If log_agent_start raises, the agent should still run and complete."""
        db = AsyncMock()
        db.log_agent_start = AsyncMock(side_effect=Exception("DB pool exhausted"))
        db.log_agent_finish = AsyncMock()
        db.log_agent_error = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        done = asyncio.Event()
        captured_result = {}

        async def fast_agent(**kw):
            return {"status": "ok"}

        runner._agent_registry["test"] = fast_agent

        async def on_broadcast(msg):
            if msg["type"] == "job_finish":
                captured_result.update(msg.get("result", {}))
                done.set()

        runner.set_broadcast_callback(on_broadcast)
        await runner.start_job("test")
        await asyncio.wait_for(done.wait(), timeout=5.0)

        # Agent ran successfully despite logging failure
        assert captured_result["status"] == "ok"
        # log_agent_finish should NOT be called since run_id is None
        db.log_agent_finish.assert_not_called()

    @pytest.mark.asyncio
    async def test_daily_pipeline_includes_learning(self):
        """Daily pipeline should include the learning step."""
        db = AsyncMock()
        db.log_agent_start = AsyncMock(return_value={"id": "run-daily"})
        db.log_agent_finish = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        step_names = []

        async def stub(**kw):
            return {"banks_processed": 1, "banks_total": 1, "banks_failed": 0}

        runner._run_scout = stub
        runner._run_strategist = stub
        runner._run_crawler = stub
        runner._run_parser = stub
        runner._run_learning = stub

        done = asyncio.Event()

        async def tracking_broadcast(msg):
            if msg["type"] == "job_step_start":
                step_names.append(msg["step"])
            if msg["type"] == "job_finish":
                done.set()

        runner.set_broadcast_callback(tracking_broadcast)
        await runner.start_job("daily")
        await asyncio.wait_for(done.wait(), timeout=5.0)

        assert "learning" in step_names
        assert step_names == ["scout", "strategist", "crawler", "parser", "learning"]

    def test_job_is_frozen(self):
        job = CrawlJob(job_id="abc", agent="scout", status=CrawlJobStatus.RUNNING)
        assert job.job_id == "abc"

    @pytest.mark.asyncio
    async def test_start_job_enqueues_to_arq(self):
        """start_job should enqueue an arq job when arq_pool is provided."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="arq-job-1"))
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        job = await runner.start_job("strategist", bank_code="bca")
        assert job is not None
        assert job.agent == "strategist"
        assert job.status == CrawlJobStatus.QUEUED

        mock_pool.enqueue_job.assert_called_once()
        call_kwargs = mock_pool.enqueue_job.call_args.kwargs
        assert call_kwargs["agent_name"] == "strategist"
        assert call_kwargs["bank_code"] == "bca"

    @pytest.mark.asyncio
    async def test_start_job_allows_concurrent_when_using_queue(self):
        """Multiple jobs should be accepted when using arq queue."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="arq-1"))
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        job1 = await runner.start_job("strategist", bank_code="bca")
        job2 = await runner.start_job("strategist", bank_code="bni")
        assert job1 is not None
        assert job2 is not None
        assert mock_pool.enqueue_job.call_count == 2

    @pytest.mark.asyncio
    async def test_inprocess_fallback_still_blocks_concurrent(self):
        """Without arq_pool, the old single-concurrency behavior should still work."""
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)  # No arq_pool

        async def slow(**kw):
            await asyncio.sleep(10)
            return {}

        runner._agent_registry["test"] = slow
        job1 = await runner.start_job("test")
        assert job1 is not None
        job2 = await runner.start_job("test")
        assert job2 is None  # Blocked
        await runner.cancel_all()

"""Tests for eng review fixes: routing, dedup, batch, reconnection, BaseException."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ceres.api.tasks import CrawlTaskRunner, CrawlJob, CrawlJobStatus


# ---------------------------------------------------------------------------
# Fix #1: Parser routes to in-process (not arq)
# ---------------------------------------------------------------------------


class TestParserInProcessRouting:
    @pytest.mark.asyncio
    async def test_parser_routes_to_inprocess_even_with_arq(self):
        """Parser agent must run in-process because it needs LLM extractor setup."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        async def fast_parser(**kw):
            return {"programs_parsed": 0, "errors": []}

        runner._agent_registry["parser"] = fast_parser
        job = await runner.start_job("parser")

        assert job is not None
        assert job.status == CrawlJobStatus.RUNNING
        mock_pool.enqueue_job.assert_not_called()
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_daily_routes_to_inprocess_even_with_arq(self):
        """Daily pipeline must run in-process because it chains multiple agents."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        async def fast_stub(**kw):
            return {"banks_processed": 0, "banks_total": 0, "banks_failed": 0}

        runner._run_scout = fast_stub
        runner._run_strategist = fast_stub
        runner._run_crawler = fast_stub
        runner._run_learning = fast_stub

        job = await runner.start_job("daily")
        assert job is not None
        assert job.status == CrawlJobStatus.RUNNING
        mock_pool.enqueue_job.assert_not_called()
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_crawler_routes_to_arq_with_pool(self):
        """Non-excluded agents should use arq when pool is available."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        job = await runner.start_job("crawler", bank_code="BCA")
        assert job is not None
        assert job.status == CrawlJobStatus.QUEUED
        mock_pool.enqueue_job.assert_called_once()


# ---------------------------------------------------------------------------
# Fix #5: arq job_id dedup
# ---------------------------------------------------------------------------


class TestArqJobDedup:
    @pytest.mark.asyncio
    async def test_enqueue_sends_dedup_id(self):
        """_enqueue_job should pass _job_id for dedup."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        await runner.start_job("strategist", bank_code="BRI", force=True)

        call_kwargs = mock_pool.enqueue_job.call_args.kwargs
        assert call_kwargs["_job_id"] == "strategist:BRI"
        assert call_kwargs["agent_name"] == "strategist"
        assert call_kwargs["force"] is True

    @pytest.mark.asyncio
    async def test_enqueue_dedup_id_without_bank_code(self):
        """Dedup ID uses 'all' when no bank_code provided."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        await runner.start_job("scout")

        call_kwargs = mock_pool.enqueue_job.call_args.kwargs
        assert call_kwargs["_job_id"] == "scout:all"


# ---------------------------------------------------------------------------
# Fix #7: enqueue_batch
# ---------------------------------------------------------------------------


class TestEnqueueBatch:
    @pytest.mark.asyncio
    async def test_batch_enqueues_all_banks_concurrently(self):
        """enqueue_batch should enqueue jobs for all bank codes."""
        db = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)

        codes = ["BCA", "BRI", "BTN"]
        results = await runner.enqueue_batch("strategist", codes, force=True)

        assert len(results) == 3
        assert all(r is not None for r in results)
        assert all(r.status == CrawlJobStatus.QUEUED for r in results)
        assert mock_pool.enqueue_job.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_inprocess_fallback_runs_single_job(self):
        """Without arq, enqueue_batch runs a single in-process job."""
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)  # No arq_pool

        async def fast_agent(**kw):
            return {"strategies_created": 3}

        runner._agent_registry["strategist"] = fast_agent

        codes = ["BCA", "BRI", "BTN"]
        results = await runner.enqueue_batch("strategist", codes, force=True)

        assert len(results) == 3
        assert results[0] is not None  # First one gets the job
        assert results[0].status == CrawlJobStatus.RUNNING
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_batch_empty_bank_codes(self):
        """enqueue_batch with empty list returns empty list."""
        db = AsyncMock()
        runner = CrawlTaskRunner(db=db)
        results = await runner.enqueue_batch("strategist", [], force=True)
        assert results == []


# ---------------------------------------------------------------------------
# Fix #10: BaseException in run_agent_task
# ---------------------------------------------------------------------------


class TestRunAgentTaskBaseException:
    @pytest.mark.asyncio
    async def test_cancelled_error_publishes_error_event(self):
        """CancelledError (BaseException) should still publish an error event."""
        from ceres.queue import run_agent_task, CHANNEL

        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_config = MagicMock()
        ctx = {"redis": mock_redis, "db": mock_db, "config": mock_config}

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(side_effect=asyncio.CancelledError())
        mock_class = MagicMock(return_value=mock_agent)

        with patch("ceres.queue._get_agent_class", return_value=mock_class):
            with pytest.raises(asyncio.CancelledError):
                await run_agent_task(
                    ctx, job_id="job-timeout", agent_name="crawler",
                )

        # Should have 2 publishes: "running" and "error"
        assert mock_redis.publish.call_count == 2
        error_payload = json.loads(mock_redis.publish.call_args_list[1].args[1])
        assert error_payload["status"] == "error"
        assert error_payload["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_agent_task_with_no_bank_code(self):
        """run_agent_task with bank_code=None should not pass it to execute."""
        from ceres.queue import run_agent_task

        mock_redis = AsyncMock()
        mock_db = AsyncMock()
        mock_config = MagicMock()
        ctx = {"redis": mock_redis, "db": mock_db, "config": mock_config}

        mock_agent = AsyncMock()
        mock_agent.execute = AsyncMock(return_value={"ok": True})
        mock_class = MagicMock(return_value=mock_agent)

        with patch("ceres.queue._get_agent_class", return_value=mock_class):
            await run_agent_task(
                ctx, job_id="job-no-bank", agent_name="scout",
                bank_code=None, force=True,
            )

        call_kwargs = mock_agent.execute.call_args.kwargs
        assert "bank_code" not in call_kwargs
        assert call_kwargs["force"] is True


# ---------------------------------------------------------------------------
# Fix #9: PubSub reconnection
# ---------------------------------------------------------------------------


class TestPubSubReconnection:
    @pytest.mark.asyncio
    async def test_listen_reconnects_on_error(self):
        """_listen should reconnect after a Redis connection error."""
        from ceres.pubsub import PubSubBridge

        broadcast = AsyncMock()
        bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

        call_count = 0

        class FakePubSub:
            async def subscribe(self, channel):
                pass

            async def unsubscribe(self, channel):
                pass

            async def listen(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("Redis gone")
                # Second call: yield one message then cancel
                yield {"type": "message", "data": json.dumps({"test": True}).encode()}
                # Simulate graceful stop
                raise asyncio.CancelledError()

        bridge._redis = MagicMock()
        bridge._redis.pubsub = MagicMock(return_value=FakePubSub())

        with pytest.raises(asyncio.CancelledError):
            # Patch sleep to avoid real delays
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await bridge._listen()

        # Should have reconnected and processed the message
        assert call_count == 2
        broadcast.assert_called_once()


# ---------------------------------------------------------------------------
# Fix #3: WorkerSettings uses from_dsn
# ---------------------------------------------------------------------------


class TestWorkerSettings:
    def test_max_tries_is_one(self):
        """max_tries should be 1 to prevent silent retries on bank sites."""
        from ceres.queue import WorkerSettings

        assert WorkerSettings.max_tries == 1

    def test_redis_settings_from_dsn(self):
        """redis_settings should be created via from_dsn, not manual parsing."""
        from ceres.queue import WorkerSettings
        from arq.connections import RedisSettings

        assert isinstance(WorkerSettings.redis_settings, RedisSettings)

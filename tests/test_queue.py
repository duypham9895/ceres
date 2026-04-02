"""Tests for the arq queue module (ceres.queue)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _event helper
# ---------------------------------------------------------------------------


def test_event_helper_produces_valid_json():
    from ceres.queue import _event

    payload = _event(
        job_id="job-123",
        agent="scout",
        bank_code="BNI",
        status="running",
        error=None,
        result=None,
    )

    assert isinstance(payload, bytes)
    data = json.loads(payload)
    assert data["job_id"] == "job-123"
    assert data["agent"] == "scout"
    assert data["bank_code"] == "BNI"
    assert data["status"] == "running"
    assert data["error"] is None
    assert data["result"] is None
    assert "timestamp" in data


def test_event_helper_with_error_and_result():
    from ceres.queue import _event

    payload = _event(
        job_id="job-456",
        agent="crawler",
        bank_code=None,
        status="error",
        error="Something went wrong",
        result={"count": 5},
    )

    data = json.loads(payload)
    assert data["status"] == "error"
    assert data["error"] == "Something went wrong"
    assert data["result"] == {"count": 5}
    assert data["bank_code"] is None


# ---------------------------------------------------------------------------
# _get_agent_class
# ---------------------------------------------------------------------------


def test_get_agent_class_returns_scout():
    from ceres.queue import _get_agent_class

    from ceres.agents.scout import ScoutAgent

    assert _get_agent_class("scout") is ScoutAgent


def test_get_agent_class_raises_for_parser():
    from ceres.queue import _get_agent_class

    with pytest.raises(ValueError, match="parser"):
        _get_agent_class("parser")


def test_get_agent_class_raises_for_unknown():
    from ceres.queue import _get_agent_class

    with pytest.raises(ValueError):
        _get_agent_class("nonexistent_agent")


# ---------------------------------------------------------------------------
# run_agent_task — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_task_publishes_events():
    from ceres.queue import run_agent_task

    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    mock_config = MagicMock()

    ctx = {"redis": mock_redis, "db": mock_db, "config": mock_config}

    fake_result = {"banks_found": 3}

    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(return_value=fake_result)

    mock_agent_class = MagicMock(return_value=mock_agent_instance)

    with patch("ceres.queue._get_agent_class", return_value=mock_agent_class):
        result = await run_agent_task(
            ctx,
            job_id="job-abc",
            agent_name="scout",
            bank_code="BCA",
            force=False,
        )

    assert result == fake_result

    # Two publish calls: "running" and "success"
    assert mock_redis.publish.call_count == 2

    first_call_channel, first_payload = mock_redis.publish.call_args_list[0].args
    second_call_channel, second_payload = mock_redis.publish.call_args_list[1].args

    from ceres.queue import CHANNEL

    assert first_call_channel == CHANNEL
    assert second_call_channel == CHANNEL

    first_data = json.loads(first_payload)
    second_data = json.loads(second_payload)

    assert first_data["status"] == "running"
    assert first_data["job_id"] == "job-abc"
    assert first_data["agent"] == "scout"

    assert second_data["status"] == "success"
    assert second_data["job_id"] == "job-abc"
    assert second_data["result"] == fake_result


# ---------------------------------------------------------------------------
# run_agent_task — error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_task_publishes_error_on_failure():
    from ceres.queue import run_agent_task

    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    mock_config = MagicMock()

    ctx = {"redis": mock_redis, "db": mock_db, "config": mock_config}

    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(side_effect=RuntimeError("crawl failed"))

    mock_agent_class = MagicMock(return_value=mock_agent_instance)

    with patch("ceres.queue._get_agent_class", return_value=mock_agent_class):
        with pytest.raises(RuntimeError, match="crawl failed"):
            await run_agent_task(
                ctx,
                job_id="job-err",
                agent_name="crawler",
                bank_code="BNI",
                force=True,
            )

    # Two publish calls: "running" and "error"
    assert mock_redis.publish.call_count == 2

    second_call_channel, second_payload = mock_redis.publish.call_args_list[1].args

    from ceres.queue import CHANNEL

    assert second_call_channel == CHANNEL

    error_data = json.loads(second_payload)
    assert error_data["status"] == "error"
    assert error_data["job_id"] == "job-err"
    assert "crawl failed" in error_data["error"]


# ---------------------------------------------------------------------------
# WorkerSettings sanity checks
# ---------------------------------------------------------------------------


def test_worker_settings_has_expected_attributes():
    from ceres.queue import WorkerSettings, run_agent_task

    assert run_agent_task in WorkerSettings.functions
    assert WorkerSettings.job_timeout == 600
    assert WorkerSettings.max_tries == 3

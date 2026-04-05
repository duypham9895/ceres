"""Tests for /api/strategies/rebuild-all and force parameter."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport
from ceres.api import create_app
from ceres.api.tasks import CrawlTaskRunner, CrawlJob, CrawlJobStatus


@pytest.mark.asyncio
async def test_trigger_crawl_passes_force_param():
    app = create_app(use_lifespan=False)
    mock_runner = MagicMock(spec=CrawlTaskRunner)
    mock_runner.start_job = AsyncMock(return_value=CrawlJob(
        job_id="j1", agent="strategist", status=CrawlJobStatus.QUEUED,
    ))
    app.state.task_runner = mock_runner

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/crawl/strategist?force=true")

    assert resp.status_code == 202
    mock_runner.start_job.assert_called_once()
    call_kwargs = mock_runner.start_job.call_args
    assert call_kwargs.kwargs.get("force") is True or (len(call_kwargs.args) > 0 and call_kwargs[1].get("force") is True)


@pytest.mark.asyncio
async def test_rebuild_all_enqueues_per_bank():
    app = create_app(use_lifespan=False)
    mock_db = AsyncMock()
    mock_db.fetch_banks = AsyncMock(return_value=[
        {"id": "uuid-1", "bank_code": "bca", "website_status": "active"},
        {"id": "uuid-2", "bank_code": "bni", "website_status": "active"},
        {"id": "uuid-3", "bank_code": "mandiri", "website_status": "inactive"},
    ])
    mock_runner = MagicMock(spec=CrawlTaskRunner)
    mock_runner.enqueue_batch = AsyncMock(return_value=[
        CrawlJob(job_id="j1", agent="strategist", status=CrawlJobStatus.QUEUED),
        CrawlJob(job_id="j2", agent="strategist", status=CrawlJobStatus.QUEUED),
    ])
    app.state.db = mock_db
    app.state.task_runner = mock_runner

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/strategies/rebuild-all")

    assert resp.status_code == 202
    data = resp.json()
    assert data["queued"] == 2  # Only active banks
    mock_runner.enqueue_batch.assert_called_once()
    call_kwargs = mock_runner.enqueue_batch.call_args.kwargs
    assert call_kwargs["force"] is True
    assert set(call_kwargs["bank_codes"]) == {"bca", "bni"}


@pytest.mark.asyncio
async def test_rebuild_all_with_no_active_banks():
    app = create_app(use_lifespan=False)
    mock_db = AsyncMock()
    mock_db.fetch_banks = AsyncMock(return_value=[
        {"id": "uuid-1", "bank_code": "dead", "website_status": "inactive"},
    ])
    mock_runner = MagicMock(spec=CrawlTaskRunner)
    mock_runner.enqueue_batch = AsyncMock(return_value=[])
    app.state.db = mock_db
    app.state.task_runner = mock_runner

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/strategies/rebuild-all")

    assert resp.status_code == 202
    data = resp.json()
    assert data["queued"] == 0

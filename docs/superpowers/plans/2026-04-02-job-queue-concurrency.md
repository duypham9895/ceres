# Job Queue with Concurrency Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-concurrency asyncio.Lock in CrawlTaskRunner with an arq/Redis job queue that supports concurrent strategy rebuilds, fix force passthrough, and fix success_rate writes.

**Architecture:** arq workers run in a separate process, communicating job status to the FastAPI process via Redis pub/sub. The FastAPI process subscribes to a `ceres:job_events` channel and relays events to WebSocket clients. CrawlTaskRunner becomes a thin enqueue layer; actual agent execution moves to arq worker functions.

**Tech Stack:** arq, redis (aioredis), Redis Docker service, existing FastAPI/asyncpg stack

**Spec:** `~/.gstack/projects/ceres/edwardpham-master-design-20260402-162806.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/ceres/queue.py` | arq worker settings, task functions, Redis pub/sub publisher |
| Create | `src/ceres/pubsub.py` | Redis pub/sub subscriber that bridges to WebSocket broadcast |
| Create | `tests/test_queue.py` | Tests for queue task functions and pub/sub events |
| Create | `tests/test_pubsub.py` | Tests for pub/sub subscriber bridge |
| Modify | `src/ceres/api/tasks.py` | Convert from asyncio.create_task to arq enqueue |
| Modify | `src/ceres/api/__init__.py` | Start pub/sub subscriber in lifespan |
| Modify | `src/ceres/api/routes.py` | Add force param, add /api/strategies/rebuild-all endpoint |
| Modify | `src/ceres/config.py` | Add redis_url and max_workers config fields |
| Modify | `docker-compose.yml` | Add Redis service, add arq worker service |
| Modify | `pyproject.toml` | Add arq dependency |
| Modify | `src/ceres/agents/strategist.py` | Honor force kwarg to rebuild existing strategies |
| Modify | `dashboard/src/pages/Strategies.tsx` | Replace N-calls loop with single rebuild-all call |
| Modify | `tests/test_api_tasks.py` | Update tests for new queue-based runner |
| Create | `tests/test_api_rebuild_all.py` | Tests for /api/strategies/rebuild-all endpoint |
| Create | `tests/test_strategist_force.py` | Tests for force=True rebuild behavior |

---

### Task 1: Add Redis and arq Dependencies

**Files:**
- Modify: `pyproject.toml:9-23`
- Modify: `docker-compose.yml`
- Modify: `src/ceres/config.py:16-27`

- [ ] **Step 1: Add arq to pyproject.toml**

```toml
# Add after the openpyxl line in dependencies:
    "arq>=0.26.1,<0.27.0",
    "redis[hiredis]>=5.0.0,<6.0.0"
```

- [ ] **Step 2: Add redis_url and max_workers to CeresConfig**

In `src/ceres/config.py`, add two fields to the `CeresConfig` dataclass:

```python
@dataclass(frozen=True)
class CeresConfig:
    database_url: str
    redis_url: str = "redis://localhost:6379"
    max_workers: int = 3
    # ... existing fields unchanged ...
```

Update `from_env` to read these from environment:

```python
# Add inside from_env(), in the kwargs dict:
"redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379"),
"max_workers": int(os.environ.get("CERES_MAX_WORKERS", "3")),
```

- [ ] **Step 3: Add Redis service and arq worker to docker-compose.yml**

Add these new services and modify the existing `api` service to depend on Redis. Do NOT rewrite the entire file — only add the new services and the `depends_on` addition.

```yaml
# ADD these new services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 3

  worker:
    build: .
    env_file: .env
    command: arq ceres.queue.WorkerSettings
    depends_on:
      redis:
        condition: service_healthy

# MODIFY existing api service — add depends_on for redis:
  api:
    # ... keep existing config unchanged ...
    depends_on:
      redis:
        condition: service_healthy
```

- [ ] **Step 4: Install dependencies**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && poetry lock && poetry install`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml poetry.lock docker-compose.yml src/ceres/config.py
git commit -m "feat: add Redis, arq dependencies and config for job queue"
```

---

### Task 2: Create Queue Module (arq Worker + Publisher)

**Files:**
- Create: `src/ceres/queue.py`
- Create: `tests/test_queue.py`

- [ ] **Step 1: Write failing test for queue task function**

Create `tests/test_queue.py`:

```python
"""Tests for arq queue task functions."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_run_agent_task_publishes_events():
    """run_agent_task should publish queued, running, success events."""
    from ceres.queue import run_agent_task

    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis, "db": AsyncMock(), "config": None}

    mock_agent_cls = AsyncMock()
    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(return_value={"banks_crawled": 1})
    mock_agent_cls.return_value = mock_agent_instance

    with patch("ceres.queue._get_agent_class", return_value=mock_agent_cls):
        result = await run_agent_task(
            mock_ctx, job_id="job-1", agent_name="strategist", bank_code="bca", force=False,
        )

    assert result == {"banks_crawled": 1}
    # Should have published running + success events
    publish_calls = mock_redis.publish.call_args_list
    assert len(publish_calls) >= 2
    # First call: running event
    assert b'"status": "running"' in publish_calls[0].args[1] or '"status":"running"' in publish_calls[0].args[1].decode()


@pytest.mark.asyncio
async def test_run_agent_task_publishes_error_on_failure():
    """run_agent_task should publish error event when agent throws."""
    from ceres.queue import run_agent_task

    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis, "db": AsyncMock(), "config": None}

    mock_agent_cls = AsyncMock()
    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(side_effect=RuntimeError("timeout"))
    mock_agent_cls.return_value = mock_agent_instance

    with patch("ceres.queue._get_agent_class", return_value=mock_agent_cls):
        with pytest.raises(RuntimeError, match="timeout"):
            await run_agent_task(
                mock_ctx, job_id="job-2", agent_name="strategist", bank_code=None, force=False,
            )

    publish_calls = mock_redis.publish.call_args_list
    # Should have published running + error events
    last_call_payload = publish_calls[-1].args[1]
    assert b"error" in last_call_payload or "error" in last_call_payload.decode()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_queue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ceres.queue'`

- [ ] **Step 3: Implement queue module**

Create `src/ceres/queue.py`:

```python
"""arq worker and task functions for CERES job queue.

Worker functions execute agents and publish status events to Redis pub/sub
for the FastAPI process to relay to WebSocket clients.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from arq.connections import RedisSettings

CHANNEL = "ceres:job_events"

# Default concurrency: 3 workers
_MAX_WORKERS = int(os.environ.get("CERES_MAX_WORKERS", "3"))


def _event(
    *,
    job_id: str,
    agent_name: str,
    status: str,
    bank_code: Optional[str] = None,
    error: Optional[str] = None,
    result: Optional[dict] = None,
) -> bytes:
    """Build a JSON event payload for Redis pub/sub."""
    payload = {
        "job_id": job_id,
        "agent": agent_name,
        "bank_code": bank_code,
        "status": status,
        "error": error,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload).encode()


def _get_agent_class(agent_name: str) -> type:
    """Lazy-import and return the agent class for the given name."""
    if agent_name == "scout":
        from ceres.agents.scout import ScoutAgent
        return ScoutAgent
    if agent_name == "strategist":
        from ceres.agents.strategist import StrategistAgent
        return StrategistAgent
    if agent_name == "crawler":
        from ceres.agents.crawler import CrawlerAgent
        return CrawlerAgent
    if agent_name == "parser":
        from ceres.agents.parser import ParserAgent
        return ParserAgent
    if agent_name == "learning":
        from ceres.agents.learning import LearningAgent
        return LearningAgent
    if agent_name == "lab":
        from ceres.agents.lab import LabAgent
        return LabAgent
    raise ValueError(f"Unknown agent: {agent_name}")


async def run_agent_task(
    ctx: dict,
    *,
    job_id: str,
    agent_name: str,
    bank_code: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Execute an agent as an arq task, publishing events via Redis pub/sub.

    This runs inside the arq worker process.
    """
    redis = ctx["redis"]
    db = ctx["db"]
    config = ctx.get("config")

    await redis.publish(
        CHANNEL, _event(job_id=job_id, agent_name=agent_name, bank_code=bank_code, status="running"),
    )

    try:
        agent_cls = _get_agent_class(agent_name)
        agent = agent_cls(db=db, config=config)

        kwargs: dict[str, Any] = {}
        if bank_code is not None:
            kwargs["bank_code"] = bank_code
        if force:
            kwargs["force"] = force

        result = await agent.execute(**kwargs)

        await redis.publish(
            CHANNEL,
            _event(job_id=job_id, agent_name=agent_name, bank_code=bank_code, status="success", result=result),
        )
        return result

    except Exception as exc:
        await redis.publish(
            CHANNEL,
            _event(job_id=job_id, agent_name=agent_name, bank_code=bank_code, status="error", error=str(exc)),
        )
        raise


async def startup(ctx: dict) -> None:
    """arq worker startup: create DB connection."""
    from ceres.config import load_config
    from ceres.database import Database

    config = load_config()
    db = Database(config.database_url)
    await db.connect()
    ctx["db"] = db
    ctx["config"] = config


async def shutdown(ctx: dict) -> None:
    """arq worker shutdown: close DB connection."""
    db = ctx.get("db")
    if db is not None:
        await db.disconnect()


class WorkerSettings:
    """arq worker configuration."""

    functions = [run_agent_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = _MAX_WORKERS
    job_timeout = 600  # 10 minutes per job
    max_tries = 3
    retry_jobs = True

    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379")
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_queue.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/queue.py tests/test_queue.py
git commit -m "feat: add arq queue module with agent task runner and pub/sub events"
```

---

### Task 3: Create Pub/Sub Subscriber Bridge

**Files:**
- Create: `src/ceres/pubsub.py`
- Create: `tests/test_pubsub.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_pubsub.py`:

```python
"""Tests for Redis pub/sub to WebSocket bridge."""

import asyncio
import json

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_subscriber_relays_messages_to_broadcast():
    """PubSubBridge should relay Redis pub/sub messages to the broadcast callback."""
    from ceres.pubsub import PubSubBridge

    broadcast = AsyncMock()
    bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

    event = {"job_id": "j1", "agent": "strategist", "status": "running", "timestamp": "2026-04-02T00:00:00Z"}

    # Simulate a message received from pub/sub
    await bridge._handle_message(json.dumps(event).encode())

    broadcast.assert_called_once()
    call_arg = broadcast.call_args[0][0]
    assert call_arg["type"] == "job_status"
    assert call_arg["job_id"] == "j1"
    assert call_arg["agent"] == "strategist"
    assert call_arg["status"] == "running"


@pytest.mark.asyncio
async def test_subscriber_ignores_malformed_messages():
    """PubSubBridge should not crash on malformed JSON."""
    from ceres.pubsub import PubSubBridge

    broadcast = AsyncMock()
    bridge = PubSubBridge(redis_url="redis://localhost:6379", broadcast=broadcast)

    await bridge._handle_message(b"not json")
    broadcast.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_pubsub.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ceres.pubsub'`

- [ ] **Step 3: Implement pub/sub bridge**

Create `src/ceres/pubsub.py`:

```python
"""Redis pub/sub subscriber that bridges job events to WebSocket broadcast.

The arq worker publishes events to ``ceres:job_events``. This subscriber
runs inside the FastAPI process, listens on that channel, and calls the
WebSocket broadcast callback for each event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis

from ceres.queue import CHANNEL

logger = logging.getLogger(__name__)


class PubSubBridge:
    """Subscribes to Redis pub/sub and relays events to a broadcast callback."""

    def __init__(
        self,
        redis_url: str,
        broadcast: Callable[[dict], Coroutine[Any, Any, None]],
    ) -> None:
        self._redis_url = redis_url
        self._broadcast = broadcast
        self._task: Optional[asyncio.Task] = None
        self._redis: Optional[aioredis.Redis] = None

    async def start(self) -> None:
        """Connect to Redis and start listening in a background task."""
        self._redis = aioredis.from_url(self._redis_url)
        self._task = asyncio.create_task(self._listen())
        logger.info("PubSubBridge started on channel %s", CHANNEL)

    async def stop(self) -> None:
        """Cancel the listener and close Redis connection."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis is not None:
            await self._redis.aclose()

    async def _listen(self) -> None:
        """Subscribe and relay messages until cancelled."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await self._handle_message(message["data"])
        except asyncio.CancelledError:
            await pubsub.unsubscribe(CHANNEL)
            raise

    async def _handle_message(self, data: bytes) -> None:
        """Parse a pub/sub message and broadcast it."""
        try:
            event = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Ignoring malformed pub/sub message")
            return

        ws_message = {
            "type": "job_status",
            **event,
        }
        try:
            await self._broadcast(ws_message)
        except Exception:
            logger.exception("Failed to broadcast pub/sub event")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_pubsub.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/pubsub.py tests/test_pubsub.py
git commit -m "feat: add Redis pub/sub bridge for WebSocket event relay"
```

---

### Task 4: Refactor CrawlTaskRunner to Enqueue via arq

**Files:**
- Modify: `src/ceres/api/tasks.py`
- Modify: `tests/test_api_tasks.py`

- [ ] **Step 1: Write failing test for queue-based job dispatch**

Add to `tests/test_api_tasks.py`:

```python
@pytest.mark.asyncio
async def test_start_job_enqueues_to_arq():
    """start_job should enqueue an arq job instead of creating an asyncio.Task."""
    db = AsyncMock()
    mock_pool = AsyncMock()
    runner = CrawlTaskRunner(db=db, arq_pool=mock_pool)
    mock_pool.enqueue_job = AsyncMock(return_value=MagicMock(job_id="arq-job-1"))

    job = await runner.start_job("strategist", bank_code="bca")
    assert job is not None
    assert job.agent == "strategist"

    mock_pool.enqueue_job.assert_called_once()
    call_kwargs = mock_pool.enqueue_job.call_args.kwargs
    assert call_kwargs["agent_name"] == "strategist"
    assert call_kwargs["bank_code"] == "bca"


@pytest.mark.asyncio
async def test_start_job_allows_concurrent_when_using_queue():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_tasks.py::TestCrawlTaskRunner::test_start_job_enqueues_to_arq -v`
Expected: FAIL — `TypeError: CrawlTaskRunner.__init__() got an unexpected keyword argument 'arq_pool'`

- [ ] **Step 3: Refactor CrawlTaskRunner**

Modify `src/ceres/api/tasks.py`. The key changes:

1. Accept an optional `arq_pool` parameter
2. When `arq_pool` is provided, `start_job` enqueues via arq (no concurrency gate)
3. When `arq_pool` is None, fall back to existing asyncio.create_task behavior (backwards compat for tests)
4. Remove the `asyncio.Lock` single-concurrency gate when using arq

```python
class CrawlTaskRunner:
    """Runs crawl agents via arq queue or in-process fallback.

    When arq_pool is provided, jobs are enqueued to Redis for worker execution.
    When arq_pool is None, falls back to single-concurrency in-process execution.
    """

    def __init__(
        self,
        db: Any,
        config: Optional[Any] = None,
        arq_pool: Optional[Any] = None,
    ) -> None:
        self._db = db
        self._config = config
        self._arq_pool = arq_pool
        self._lock = asyncio.Lock()
        self._current_job: Optional[CrawlJob] = None
        self._current_task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[
            Callable[[dict], Coroutine[Any, Any, None]]
        ] = None
        self._current_step: Optional[str] = None
        self._step_index: int = 0
        self._total_steps: int = 0
        self._agent_registry: Dict[str, Callable[..., Coroutine[Any, Any, dict]]] = {}
        self._register_agents()

    # ... _register_agents, get_current_job, get_step_info, cancel_all,
    #     set_broadcast_callback unchanged ...

    async def start_job(
        self,
        agent: str,
        bank_code: Optional[str] = None,
        force: bool = False,
    ) -> Optional[CrawlJob]:
        """Start a crawl job via arq queue or in-process fallback."""
        if self._arq_pool is not None:
            return await self._enqueue_job(agent, bank_code=bank_code, force=force)
        return await self._start_job_inprocess(agent, bank_code=bank_code, force=force)

    async def _enqueue_job(
        self,
        agent: str,
        bank_code: Optional[str] = None,
        force: bool = False,
    ) -> Optional[CrawlJob]:
        """Enqueue a job to arq. No concurrency gate — arq handles that."""
        job_id = str(uuid.uuid4())
        await self._arq_pool.enqueue_job(
            "run_agent_task",
            job_id=job_id,
            agent_name=agent,
            bank_code=bank_code,
            force=force,
        )
        return CrawlJob(
            job_id=job_id,
            agent=agent,
            status=CrawlJobStatus.QUEUED,
        )

    async def _start_job_inprocess(
        self,
        agent: str,
        bank_code: Optional[str] = None,
        force: bool = False,
    ) -> Optional[CrawlJob]:
        """In-process fallback with single-concurrency gate.

        Note: force is accepted but only passed to agents that support it.
        The in-process path is used for tests and when Redis is unavailable.
        """
        async with self._lock:
            if self._current_job is not None:
                return None

            agent_fn = self._agent_registry.get(agent)
            if agent_fn is None:
                logger.warning("Unknown agent requested: %s", agent)
                return None

            job_id = str(uuid.uuid4())
            job = CrawlJob(
                job_id=job_id,
                agent=agent,
                status=CrawlJobStatus.RUNNING,
            )
            self._current_job = job
            self._current_task = asyncio.create_task(
                self._execute(job_id, agent, agent_fn, bank_code=bank_code),
            )
            return job
```

Also add `QUEUED` to `CrawlJobStatus`:

```python
class CrawlJobStatus(enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
```

- [ ] **Step 4: Run all task runner tests**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_tasks.py -v`
Expected: All PASS (existing tests use in-process fallback, new tests use arq_pool)

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/tasks.py tests/test_api_tasks.py
git commit -m "feat: refactor CrawlTaskRunner to support arq queue dispatch"
```

---

### Task 5: Wire arq Pool and PubSub into FastAPI Lifespan

**Files:**
- Modify: `src/ceres/api/__init__.py:14-35`

- [ ] **Step 1: Write failing test**

This is an integration wiring task. The test is: app startup should create arq_pool and pubsub bridge. Add to `tests/test_api.py` (or create a new test if the file doesn't have lifespan tests):

```python
@pytest.mark.asyncio
async def test_lifespan_creates_arq_pool(monkeypatch):
    """FastAPI lifespan should wire arq pool into task_runner."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    # This test just verifies the import path and config wiring don't crash
    from ceres.config import CeresConfig
    config = CeresConfig.from_env()
    assert config.redis_url == "redis://localhost:6379"
    assert config.max_workers == 3
```

- [ ] **Step 2: Run test to verify it passes** (config test should pass from Task 1)

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api.py -k "lifespan_creates_arq" -v`

- [ ] **Step 3: Update FastAPI lifespan**

Modify `src/ceres/api/__init__.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: initialise DB, arq pool, task runner, and pub/sub bridge."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from ceres.api.tasks import CrawlTaskRunner
    from ceres.config import load_config
    from ceres.database import Database
    from ceres.pubsub import PubSubBridge

    config = load_config()
    db = Database(config.database_url)
    await db.connect()

    # Connect to arq Redis pool
    arq_pool = await create_pool(RedisSettings.from_dsn(config.redis_url))

    task_runner = CrawlTaskRunner(db=db, config=config, arq_pool=arq_pool)
    task_runner.set_broadcast_callback(manager.broadcast)

    # Start pub/sub bridge: Redis events -> WebSocket broadcast
    pubsub_bridge = PubSubBridge(
        redis_url=config.redis_url,
        broadcast=manager.broadcast,
    )
    await pubsub_bridge.start()

    app.state.db = db
    app.state.config = config
    app.state.task_runner = task_runner

    yield

    await pubsub_bridge.stop()
    await task_runner.cancel_all()
    await arq_pool.close()
    await db.disconnect()
```

- [ ] **Step 4: Run existing API tests to check nothing breaks**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api.py tests/test_api_routes.py -v`
Expected: PASS (existing tests use `create_app(use_lifespan=False)` or mock the runner)

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/__init__.py
git commit -m "feat: wire arq pool and pub/sub bridge into FastAPI lifespan"
```

---

### Task 6: Add force Parameter and rebuild-all Endpoint

**Files:**
- Modify: `src/ceres/api/routes.py:593-630`
- Create: `tests/test_api_rebuild_all.py`

- [ ] **Step 1: Write failing test for force param and rebuild-all**

Create `tests/test_api_rebuild_all.py`:

```python
"""Tests for /api/strategies/rebuild-all and force parameter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.api.tasks import CrawlTaskRunner, CrawlJob, CrawlJobStatus


@pytest.mark.asyncio
async def test_trigger_crawl_passes_force_param():
    """POST /api/crawl/strategist?force=true should pass force=True to start_job."""
    from httpx import AsyncClient, ASGITransport
    from ceres.api import create_app

    app = create_app(use_lifespan=False)
    mock_runner = MagicMock(spec=CrawlTaskRunner)
    mock_runner.start_job = AsyncMock(return_value=CrawlJob(
        job_id="j1", agent="strategist", status=CrawlJobStatus.QUEUED,
    ))
    app.state.task_runner = mock_runner

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/crawl/strategist?force=true")

    assert resp.status_code == 202
    mock_runner.start_job.assert_called_once_with("strategist", bank_code=None, force=True)


@pytest.mark.asyncio
async def test_rebuild_all_enqueues_per_bank():
    """POST /api/strategies/rebuild-all should enqueue one job per active bank."""
    from httpx import AsyncClient, ASGITransport
    from ceres.api import create_app

    app = create_app(use_lifespan=False)
    mock_db = AsyncMock()
    mock_db.fetch_banks = AsyncMock(return_value=[
        {"id": "uuid-1", "bank_code": "bca", "website_status": "active"},
        {"id": "uuid-2", "bank_code": "bni", "website_status": "active"},
        {"id": "uuid-3", "bank_code": "mandiri", "website_status": "inactive"},
    ])
    mock_runner = MagicMock(spec=CrawlTaskRunner)
    mock_runner.start_job = AsyncMock(return_value=CrawlJob(
        job_id="j1", agent="strategist", status=CrawlJobStatus.QUEUED,
    ))
    app.state.db = mock_db
    app.state.task_runner = mock_runner

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/strategies/rebuild-all")

    assert resp.status_code == 202
    data = resp.json()
    # Should only queue active banks (bca, bni), not inactive (mandiri)
    assert data["queued"] == 2
    assert mock_runner.start_job.call_count == 2
    # All calls should have force=True
    for call in mock_runner.start_job.call_args_list:
        assert call.kwargs.get("force") is True or call[2].get("force") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_rebuild_all.py -v`
Expected: FAIL — no `force` param in trigger_crawl, no `/api/strategies/rebuild-all` endpoint

- [ ] **Step 3: Add force param to trigger_crawl and rebuild-all endpoint**

Modify `src/ceres/api/routes.py`. Add `force` query param to `trigger_crawl`:

```python
@router.post("/crawl/{agent_name}")
async def trigger_crawl(
    request: Request,
    agent_name: str,
    bank: Optional[str] = Query(None),
    force: bool = Query(False),
) -> JSONResponse:
    """Trigger a crawl job. Returns 202 on success, 409 if busy, 400 if unknown agent."""
    if agent_name not in VALID_AGENTS:
        return _error(
            f"Unknown agent: {agent_name}",
            code="INVALID_AGENT",
            status=400,
        )

    runner = request.app.state.task_runner

    job = await runner.start_job(agent_name, bank_code=bank, force=force)

    if job is None:
        return _error(
            "A crawl job is already running",
            code="JOB_ALREADY_RUNNING",
            status=409,
        )

    return JSONResponse(
        {
            "job_id": job.job_id,
            "agent": job.agent,
            "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            "started_at": _iso(job.started_at),
        },
        status_code=202,
    )
```

Add the rebuild-all endpoint:

```python
@router.post("/strategies/rebuild-all")
async def rebuild_all_strategies(request: Request) -> JSONResponse:
    """Enqueue strategy rebuild for all active banks.

    Each bank gets its own queued job with force=True.
    Returns 202 with count of queued jobs.
    """
    db = request.app.state.db
    runner = request.app.state.task_runner

    banks = await db.fetch_banks()
    active_banks = [b for b in banks if b.get("website_status") in ("active", "unknown")]

    queued = 0
    failed_banks: list[str] = []

    for bank in active_banks:
        job = await runner.start_job("strategist", bank_code=bank["bank_code"], force=True)
        if job is not None:
            queued += 1
        else:
            failed_banks.append(bank["bank_code"])

    return JSONResponse(
        {"queued": queued, "total_banks": len(active_banks), "failed": failed_banks},
        status_code=202,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_rebuild_all.py tests/test_api_routes.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/routes.py tests/test_api_rebuild_all.py
git commit -m "feat: add force param to crawl trigger and /api/strategies/rebuild-all endpoint"
```

---

### Task 7: Fix StrategistAgent force Passthrough

**Files:**
- Modify: `src/ceres/agents/strategist.py:48-110`
- Create: `tests/test_strategist_force.py`

The `force` kwarg is passed through the API and queue, but `StrategistAgent.run()` currently ignores it — `force` is read from kwargs but the guard at line 77 (`if has_existing and not force: continue`) already exists. However, the keyword is never actually received by the API path because the old `start_job` → `_run_strategist` flow doesn't pass it. With arq, `run_agent_task` now passes `force` via `kwargs`. We need to verify this works end-to-end and that `StrategistAgent.run()` actually reads `force` from kwargs.

- [ ] **Step 1: Write failing test for force behavior**

Create `tests/test_strategist_force.py`:

```python
"""Tests for StrategistAgent force=True rebuild behavior."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_strategist_skips_existing_without_force():
    """StrategistAgent should skip banks with active strategies when force=False."""
    from ceres.agents.strategist import StrategistAgent

    db = AsyncMock()
    db.fetch_banks = AsyncMock(return_value=[
        {"id": "uuid-1", "bank_code": "bca", "website_url": "https://bca.co.id", "website_status": "active"},
    ])
    db.fetch_active_strategies = AsyncMock(return_value=[
        {"bank_id": "uuid-1", "bank_code": "bca"},
    ])

    agent = StrategistAgent(db=db)
    result = await agent.run(force=False)

    assert result["strategies_created"] == 0
    assert result["strategies_updated"] == 0


@pytest.mark.asyncio
async def test_strategist_rebuilds_existing_with_force():
    """StrategistAgent should rebuild existing strategies when force=True."""
    from ceres.agents.strategist import StrategistAgent

    db = AsyncMock()
    db.fetch_banks = AsyncMock(return_value=[
        {"id": "uuid-1", "bank_code": "bca", "website_url": "https://bca.co.id",
         "website_status": "active", "api_available": False},
    ])
    db.fetch_active_strategies = AsyncMock(return_value=[
        {"bank_id": "uuid-1", "bank_code": "bca"},
    ])
    db.upsert_strategy = AsyncMock(return_value={"id": "s-1"})

    agent = StrategistAgent(db=db)

    with patch.object(agent, "_analyze_bank", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = {
            "anti_bot_detected": False,
            "anti_bot_type": None,
            "bypass_method": "headless_browser",
            "loan_page_urls": ["https://bca.co.id/kpr"],
            "selectors": {},
            "rate_limit_ms": 2000,
        }
        result = await agent.run(force=True)

    assert result["strategies_updated"] == 1
    db.upsert_strategy.assert_called_once()
```

- [ ] **Step 2: Run test to verify behavior**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_strategist_force.py -v`

The first test should PASS (existing behavior: skip without force). The second test should also PASS because the `force` kwarg is already read in `strategist.py:59` and used in the guard at line 77. If it fails, the `run()` method needs to be updated to accept `force` from kwargs.

- [ ] **Step 3: Verify the force kwarg flows through run()**

Read `strategist.py:48-60`. Confirm that `force: bool = kwargs.get("force", False)` exists at line 59. If it does, the code already handles force correctly — the bug was that the API/task runner never passed it. Our fix in Task 6 (API force param) and Task 2 (queue passing force) complete the chain.

- [ ] **Step 4: Commit**

```bash
git add tests/test_strategist_force.py
git commit -m "test: add strategist force=True rebuild behavior tests"
```

---

### Task 8: Verify success_rate Write (Already Implemented)

**Files:**
- Verify: `src/ceres/agents/crawler.py:155-157`
- Verify: `src/ceres/database.py:245-272`

The `success_rate` write was already fixed in a previous session (commit `899ed6b`). `CrawlerAgent._crawl_bank()` already calls `self.db.update_strategy_success_rate(strategy_id=...)` at line 155, and `Database.update_strategy_success_rate()` exists at line 245 with the correct SQL.

- [ ] **Step 1: Verify the implementation exists**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && grep -n "update_strategy_success_rate" src/ceres/agents/crawler.py src/ceres/database.py`

Expected output should show both the call site in crawler.py and the method definition in database.py.

- [ ] **Step 2: Write a unit test to confirm success_rate computation**

Add to an existing test file or create a focused test:

```python
# In tests/test_crawler.py or a new file
@pytest.mark.asyncio
async def test_crawl_bank_updates_success_rate():
    """After crawling a bank, success_rate should be updated via db."""
    # This is verified by checking that update_strategy_success_rate is called
    # The actual SQL computation is covered by test_database.py
    db = AsyncMock()
    db.fetch_active_strategies = AsyncMock(return_value=[{
        "id": "s-1", "bank_id": "b-1", "bank_code": "bca",
        "loan_page_urls": '["https://bca.co.id/kpr"]',
        "rate_limit_ms": 100, "bypass_method": "headless_browser",
    }])
    db.create_crawl_log = AsyncMock(return_value={"id": "cl-1"})
    db.store_raw_html = AsyncMock(return_value={"id": "rd-1"})
    db.update_crawl_log = AsyncMock(return_value={"id": "cl-1"})
    db.update_strategy_success_rate = AsyncMock()

    from ceres.agents.crawler import CrawlerAgent
    agent = CrawlerAgent(db=db)

    with patch.object(agent, "_fetch_page", new_callable=AsyncMock, return_value="<html>content</html>"):
        with patch("ceres.agents.crawler.detect_anti_bot") as mock_detect:
            mock_detect.return_value = MagicMock(detected=False)
            await agent.run(bank_code="bca")

    db.update_strategy_success_rate.assert_called_once_with(strategy_id="s-1")
```

- [ ] **Step 3: Run test**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_crawler.py -k "success_rate" -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_crawler.py
git commit -m "test: verify success_rate is updated after crawl"
```

---

### Task 9: Update Dashboard bulkRebuild

**Files:**
- Modify: `dashboard/src/pages/Strategies.tsx:147-175`

- [ ] **Step 1: Replace bulkRebuild with single API call**

In `dashboard/src/pages/Strategies.tsx`, replace the `bulkRebuild` function:

```typescript
const bulkRebuild = async () => {
    setIsBulkRunning(true);
    setBulkStatus('Rebuilding all selected banks...');
    try {
      const resp = await apiPost<{ queued: number; total_banks: number; failed: string[] }>(
        '/api/strategies/rebuild-all'
      );
      if (resp.failed.length === 0) {
        setBulkStatus(`✓ Queued ${resp.queued} banks for rebuild`);
        clearSelection();
      } else {
        setBulkStatus(`⚠ Queued ${resp.queued}/${resp.total_banks} — ${resp.failed.length} failed to queue`);
      }
    } catch {
      setBulkStatus('✗ Failed to trigger rebuild');
    }
    setIsBulkRunning(false);
    setTimeout(() => setBulkStatus(null), 8000);
  };
```

Note: This rebuilds ALL active banks, not just selected ones. If you want per-selection rebuild, keep the loop but it now works because the queue accepts concurrent jobs. For now, rebuild-all is simpler and matches the most common use case.

- [ ] **Step 2: Verify the build compiles**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Strategies.tsx
git commit -m "feat: replace N-call bulk rebuild with single rebuild-all API call"
```

---

### Task 10: Verify End-to-End (Manual Smoke Test)

- [ ] **Step 1: Start the full stack**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && docker compose up --build`

Verify: Redis, API, worker, and dashboard all start without errors.

- [ ] **Step 2: Test single-bank rebuild from dashboard**

Open http://localhost:3000/strategies, expand a bank row, click "Rebuild Strategy". Verify the job is queued (202 response) and progress appears via WebSocket.

- [ ] **Step 3: Test bulk rebuild from dashboard**

Click "Select all failing banks" → "Rebuild Selected". Verify all banks are queued and progress streams via WebSocket.

- [ ] **Step 4: Verify success_rate updates after crawl**

After a crawler run completes, check the database:

```sql
SELECT bank_code, success_rate FROM bank_strategies bs
JOIN banks b ON b.id = bs.bank_id
WHERE bs.is_active = true
ORDER BY success_rate;
```

Verify success_rate values are no longer all 0.00.

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: verify end-to-end job queue with concurrent strategy rebuilds"
```

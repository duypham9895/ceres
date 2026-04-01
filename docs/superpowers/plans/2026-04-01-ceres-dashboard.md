# CERES Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full ops dashboard (React + FastAPI + Docker) that replaces the CLI as the primary way to operate CERES — trigger crawls, monitor progress, browse data.

**Architecture:** FastAPI backend exposes REST + WebSocket API over the existing CERES database and agents. React frontend (Vite + Tailwind + shadcn/ui) consumes the API. Both run in Docker Compose containers. Crawl jobs run via `asyncio.create_task` with a single-concurrency gate and WebSocket progress broadcasting.

**Tech Stack:** FastAPI, asyncpg, React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Recharts, React Router, Docker Compose

**Spec:** `~/.gstack/projects/ceres/edwardpham-master-design-20260401-120000.md`

---

## Phase 1: FastAPI Backend API

### Task 1: FastAPI App Factory + Dependencies

**Files:**
- Create: `src/ceres/api/__init__.py`
- Create: `src/ceres/api/routes.py` (stub)
- Create: `src/ceres/api/websocket.py` (stub)
- Create: `src/ceres/api/tasks.py` (stub)
- Modify: `pyproject.toml` (add fastapi, uvicorn, websockets)
- Create: `tests/test_api.py`

- [ ] **Step 1: Add FastAPI dependencies**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
poetry add fastapi uvicorn[standard] websockets
```

- [ ] **Step 2: Write failing test for app factory**

`tests/test_api.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport

from ceres.api import create_app


class TestAppFactory:
    @pytest.mark.asyncio
    async def test_health_check(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_cors_headers(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.options(
                "/api/status",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers
```

- [ ] **Step 3: Run test to verify it fails**

```bash
poetry add --group dev httpx
poetry run pytest tests/test_api.py -v
```

- [ ] **Step 4: Implement app factory**

`src/ceres/api/__init__.py`:
```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="CERES API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from ceres.api.routes import router
    app.include_router(router, prefix="/api")

    return app


app = create_app()
```

`src/ceres/api/routes.py`:
```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def health_check():
    return {"status": "ok"}
```

`src/ceres/api/websocket.py`:
```python
# WebSocket handler — implemented in Task 3
```

`src/ceres/api/tasks.py`:
```python
# Crawl task runner — implemented in Task 2
```

- [ ] **Step 5: Run test, verify pass**

```bash
poetry run pytest tests/test_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/ceres/api/ tests/test_api.py pyproject.toml poetry.lock
git commit -m "feat: add FastAPI app factory with CORS and health check"
```

---

### Task 2: Crawl Task Runner

**Files:**
- Create: `src/ceres/api/tasks.py`
- Create: `tests/test_api_tasks.py`

- [ ] **Step 1: Write failing test**

`tests/test_api_tasks.py`:
```python
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
        # Clean up
        await runner.cancel_all()

    @pytest.mark.asyncio
    async def test_concurrent_jobs_blocked(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[])
        runner = CrawlTaskRunner(db=db)

        # Start a long-running job
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
        db.fetch_banks = AsyncMock(return_value=[])
        runner = CrawlTaskRunner(db=db)

        async def fast_agent(**kwargs):
            return {"banks_checked": 0}

        runner._agent_registry["test"] = fast_agent
        job = await runner.start_job("test")
        # Wait for completion
        await asyncio.sleep(0.1)
        assert runner.get_current_job() is None

    def test_job_is_frozen(self):
        job = CrawlJob(job_id="abc", agent="scout", status=CrawlJobStatus.RUNNING)
        assert job.job_id == "abc"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_api_tasks.py -v
```

- [ ] **Step 3: Implement task runner**

`src/ceres/api/tasks.py`:
```python
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from ceres.database import Database

logger = logging.getLogger(__name__)


class CrawlJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class CrawlJob:
    job_id: str
    agent: str
    status: CrawlJobStatus
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: Optional[dict] = None
    error: Optional[str] = None


class CrawlTaskRunner:
    def __init__(self, db: Database, config: Optional[Any] = None):
        self.db = db
        self.config = config
        self._lock = asyncio.Lock()
        self._current_job: Optional[CrawlJob] = None
        self._current_task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[Callable] = None
        self._agent_registry: dict[str, Callable] = {}
        self._register_agents()

    def set_broadcast_callback(self, callback: Callable) -> None:
        self._broadcast_callback = callback

    def _register_agents(self) -> None:
        self._agent_registry = {
            "daily": self._run_daily,
            "scout": self._run_scout,
            "strategist": self._run_strategist,
            "crawler": self._run_crawler,
            "parser": self._run_parser,
            "learning": self._run_learning,
            "lab": self._run_lab,
        }

    async def start_job(
        self, agent: str, bank_code: Optional[str] = None, **kwargs
    ) -> Optional[CrawlJob]:
        async with self._lock:
            if self._current_job is not None:
                return None

            job_id = str(uuid.uuid4())
            job = CrawlJob(
                job_id=job_id,
                agent=agent,
                status=CrawlJobStatus.RUNNING,
            )
            self._current_job = job

        agent_fn = self._agent_registry.get(agent)
        if not agent_fn:
            async with self._lock:
                self._current_job = None
            return None

        self._current_task = asyncio.create_task(
            self._execute(job_id, agent, agent_fn, bank_code=bank_code, **kwargs)
        )
        return job

    async def _execute(
        self, job_id: str, agent: str, agent_fn: Callable, **kwargs
    ) -> None:
        await self._broadcast({
            "event": "crawl_started",
            "job_id": job_id,
            "agent": agent,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            result = await agent_fn(**kwargs)
            await self._broadcast({
                "event": "crawl_finished",
                "job_id": job_id,
                "status": "success",
                "result": result or {},
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.error(f"Crawl job {job_id} failed: {e}")
            await self._broadcast({
                "event": "crawl_error",
                "job_id": job_id,
                "agent": agent,
                "error": str(e),
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            async with self._lock:
                self._current_job = None
                self._current_task = None

    def get_current_job(self) -> Optional[CrawlJob]:
        return self._current_job

    async def cancel_all(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            self._current_job = None
            self._current_task = None

    async def _broadcast(self, message: dict) -> None:
        if self._broadcast_callback:
            await self._broadcast_callback(message)

    # ── Agent runners ──

    async def _run_daily(self, **kwargs) -> dict:
        from ceres.agents.scout import ScoutAgent
        from ceres.agents.crawler import CrawlerAgent
        from ceres.agents.parser import ParserAgent
        from ceres.agents.learning import LearningAgent

        results = {}
        for name, cls in [
            ("scout", ScoutAgent),
            ("crawler", CrawlerAgent),
            ("parser", ParserAgent),
            ("learning", LearningAgent),
        ]:
            await self._broadcast({
                "event": "crawl_progress",
                "job_id": self._current_job.job_id if self._current_job else "",
                "agent": name,
                "message": f"Running {name}...",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            agent = cls(db=self.db, config=self.config)
            results[name] = await agent.execute(**kwargs)
        return results

    async def _run_scout(self, **kwargs) -> dict:
        from ceres.agents.scout import ScoutAgent
        agent = ScoutAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)

    async def _run_strategist(self, **kwargs) -> dict:
        from ceres.agents.strategist import StrategistAgent
        agent = StrategistAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)

    async def _run_crawler(self, **kwargs) -> dict:
        from ceres.agents.crawler import CrawlerAgent
        agent = CrawlerAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)

    async def _run_parser(self, **kwargs) -> dict:
        from ceres.agents.parser import ParserAgent
        agent = ParserAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)

    async def _run_learning(self, **kwargs) -> dict:
        from ceres.agents.learning import LearningAgent
        agent = LearningAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)

    async def _run_lab(self, **kwargs) -> dict:
        from ceres.agents.lab import LabAgent
        agent = LabAgent(db=self.db, config=self.config)
        return await agent.execute(**kwargs)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
poetry run pytest tests/test_api_tasks.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/tasks.py tests/test_api_tasks.py
git commit -m "feat: add crawl task runner with single-concurrency gate and WebSocket broadcasting"
```

---

### Task 3: WebSocket Handler

**Files:**
- Modify: `src/ceres/api/websocket.py`
- Modify: `src/ceres/api/__init__.py`
- Create: `tests/test_api_websocket.py`

- [ ] **Step 1: Write failing test**

`tests/test_api_websocket.py`:
```python
import pytest
from unittest.mock import AsyncMock

from ceres.api.websocket import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_adds_to_active(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        assert len(manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes(self):
        manager = ConnectionManager()
        ws = AsyncMock()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast({"event": "test"})
        ws1.send_json.assert_called_once_with({"event": "test"})
        ws2.send_json.assert_called_once_with({"event": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self):
        manager = ConnectionManager()
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_json.side_effect = Exception("closed")
        await manager.connect(ws_good)
        await manager.connect(ws_bad)
        await manager.broadcast({"event": "test"})
        assert len(manager.active_connections) == 1
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement WebSocket handler**

`src/ceres/api/websocket.py`:
```python
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)
```

- [ ] **Step 4: Wire WebSocket into app**

Update `src/ceres/api/__init__.py` to add the WebSocket route:

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ceres.api.websocket import ConnectionManager
from ceres.api.tasks import CrawlTaskRunner
from ceres.config import load_config
from ceres.database import Database

manager = ConnectionManager()
task_runner: Optional[CrawlTaskRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global task_runner
    config = load_config()
    db = Database(config.database_url)
    await db.connect()

    task_runner = CrawlTaskRunner(db=db, config=config)
    task_runner.set_broadcast_callback(manager.broadcast)

    app.state.db = db
    app.state.config = config
    app.state.task_runner = task_runner

    yield

    await db.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(title="CERES API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from ceres.api.routes import router
    app.include_router(router, prefix="/api")

    @app.websocket("/ws/crawl-status")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                # Client sends {"subscribe": "all"} — acknowledged
                if data.get("subscribe") == "all":
                    await websocket.send_json({"event": "subscribed"})
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()
```

- [ ] **Step 5: Update test_api.py to handle lifespan**

The existing `test_api.py` tests need a version of `create_app` that doesn't require a real DB. Update test to mock the lifespan or create a test-specific app. Simplest: patch the lifespan.

- [ ] **Step 6: Run tests, verify pass**

```bash
poetry run pytest tests/test_api_websocket.py tests/test_api.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/ceres/api/ tests/test_api_websocket.py tests/test_api.py
git commit -m "feat: add WebSocket connection manager with broadcast and lifespan wiring"
```

---

### Task 4: REST Routes — Read Endpoints

**Files:**
- Modify: `src/ceres/api/routes.py`
- Create: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_routes.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.api.routes import router
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


def make_test_app(mock_db):
    app = FastAPI()
    app.state.db = mock_db
    app.state.task_runner = MagicMock()
    app.state.task_runner.get_current_job.return_value = None
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


class TestBanksRoute:
    @pytest.mark.asyncio
    async def test_list_banks_with_pagination(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchval = AsyncMock(return_value=58)
        db.pool.fetch = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "bank_name": "Bank Central Asia",
             "bank_category": "SWASTA_NASIONAL", "bank_type": "KONVENSIONAL",
             "website_status": "active", "last_crawled_at": None, "programs_count": 0}
        ])
        app = make_test_app(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/banks?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data


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
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement read routes**

`src/ceres/api/routes.py`:
```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()


def _get_db(request: Request):
    return request.app.state.db


def _get_runner(request: Request):
    return request.app.state.task_runner


@router.get("/status")
async def health_check(request: Request):
    runner = _get_runner(request)
    current_job = runner.get_current_job() if runner else None
    return {
        "status": "ok",
        "crawl_running": current_job is not None,
        "current_job": current_job.agent if current_job else None,
    }


@router.get("/dashboard")
async def dashboard_overview(request: Request):
    db = _get_db(request)
    banks = await db.fetch_banks()
    programs = await db.fetch_loan_programs()
    stats = await db.get_crawl_stats()

    active = sum(1 for b in banks if b.get("website_status") == "active")
    unreachable = sum(1 for b in banks if b.get("website_status") == "unreachable")
    blocked = sum(1 for b in banks if b.get("website_status") == "blocked")

    total_crawls = stats.get("total_crawls") or 0
    successes = stats.get("successes") or 0
    success_rate = round(successes / total_crawls, 2) if total_crawls > 0 else 0

    return {
        "total_banks": len(banks),
        "banks_active": active,
        "banks_unreachable": unreachable,
        "banks_blocked": blocked,
        "total_programs": len(programs),
        "success_rate": success_rate,
        "total_crawls_7d": total_crawls,
        "successes_7d": successes,
        "failures_7d": stats.get("failures") or 0,
        "blocked_7d": stats.get("blocked") or 0,
    }


@router.get("/banks")
async def list_banks(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
):
    db = _get_db(request)
    offset = (page - 1) * limit

    where = ""
    args = []
    if category:
        where = "WHERE bank_category = $1"
        args.append(category)

    count_sql = f"SELECT COUNT(*) FROM banks {where}"
    total = await db.pool.fetchval(count_sql, *args)

    idx = len(args) + 1
    data_sql = f"""
        SELECT b.*, COALESCE(lp.cnt, 0) as programs_count
        FROM banks b
        LEFT JOIN (
            SELECT bank_id, COUNT(*) as cnt FROM loan_programs
            WHERE is_latest = true GROUP BY bank_id
        ) lp ON b.id = lp.bank_id
        {where}
        ORDER BY b.bank_code
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    rows = await db.pool.fetch(data_sql, *args, limit, offset)

    return {
        "data": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/banks/{bank_id}")
async def get_bank(request: Request, bank_id: str):
    db = _get_db(request)
    bank = await db.pool.fetchrow("SELECT * FROM banks WHERE id = $1", bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail={"error": "Bank not found", "code": "BANK_NOT_FOUND"})

    programs = await db.fetch_loan_programs(bank_id=bank_id)
    strategies = await db.fetch_active_strategies(bank_id=bank_id)

    logs = await db.pool.fetch(
        "SELECT * FROM crawl_logs WHERE bank_id = $1 ORDER BY started_at DESC LIMIT 20",
        bank_id,
    )

    return {
        "bank": dict(bank),
        "programs": programs,
        "strategies": [dict(s) for s in strategies] if strategies else [],
        "crawl_logs": [dict(l) for l in logs],
    }


@router.get("/crawl-logs")
async def list_crawl_logs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    bank_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    db = _get_db(request)
    offset = (page - 1) * limit

    conditions = []
    args = []
    idx = 1
    if status:
        conditions.append(f"cl.status = ${idx}")
        args.append(status)
        idx += 1
    if bank_id:
        conditions.append(f"cl.bank_id = ${idx}")
        args.append(bank_id)
        idx += 1
    if date_from:
        conditions.append(f"cl.started_at >= ${idx}::timestamptz")
        args.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"cl.started_at <= ${idx}::timestamptz")
        args.append(date_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM crawl_logs cl {where}", *args
    )

    rows = await db.pool.fetch(
        f"""SELECT cl.*, b.bank_code, b.bank_name
            FROM crawl_logs cl
            JOIN banks b ON cl.bank_id = b.id
            {where}
            ORDER BY cl.started_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *args, limit, offset,
    )

    return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}


@router.get("/loan-programs")
async def list_loan_programs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    bank_id: Optional[str] = None,
    loan_type: Optional[str] = None,
    sort: Optional[str] = "program_name",
):
    db = _get_db(request)
    offset = (page - 1) * limit

    conditions = ["lp.is_latest = true"]
    args = []
    idx = 1
    if bank_id:
        conditions.append(f"lp.bank_id = ${idx}")
        args.append(bank_id)
        idx += 1
    if loan_type:
        conditions.append(f"lp.loan_type = ${idx}")
        args.append(loan_type)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"

    allowed_sorts = {"program_name", "min_interest_rate", "max_interest_rate",
                     "data_confidence", "completeness_score", "created_at"}
    order = sort if sort in allowed_sorts else "program_name"

    total = await db.pool.fetchval(
        f"SELECT COUNT(*) FROM loan_programs lp {where}", *args
    )

    rows = await db.pool.fetch(
        f"""SELECT lp.*, b.bank_code, b.bank_name
            FROM loan_programs lp
            JOIN banks b ON lp.bank_id = b.id
            {where}
            ORDER BY lp.{order}
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *args, limit, offset,
    )

    return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}


@router.get("/strategies")
async def list_strategies(request: Request):
    db = _get_db(request)
    rows = await db.pool.fetch("""
        SELECT bs.*, b.bank_code, b.bank_name
        FROM bank_strategies bs
        JOIN banks b ON bs.bank_id = b.id
        WHERE bs.is_active = true
        ORDER BY b.bank_code
    """)
    return {"data": [dict(r) for r in rows]}


@router.get("/recommendations")
async def list_recommendations(request: Request):
    db = _get_db(request)
    rows = await db.pool.fetch(
        "SELECT * FROM ringkas_recommendations ORDER BY priority, created_at DESC"
    )
    return {"data": [dict(r) for r in rows]}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
poetry run pytest tests/test_api_routes.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/routes.py tests/test_api_routes.py
git commit -m "feat: add REST read endpoints with pagination for dashboard, banks, logs, programs"
```

---

### Task 5: REST Routes — Crawl Trigger Endpoints

**Files:**
- Modify: `src/ceres/api/routes.py`
- Modify: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_api_routes.py`:
```python
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
        app = FastAPI()
        app.state.db = db
        app.state.task_runner = runner
        app.include_router(router, prefix="/api")
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
        runner.start_job = AsyncMock(return_value=None)  # Blocked
        app = FastAPI()
        app.state.db = db
        app.state.task_runner = runner
        app.include_router(router, prefix="/api")
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
        app = FastAPI()
        app.state.db = db
        app.state.task_runner = runner
        app.include_router(router, prefix="/api")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/crawl/crawler?bank=BCA")
        assert resp.status_code == 202
        runner.start_job.assert_called_once_with("crawler", bank_code="BCA")
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add crawl trigger routes**

Add to `src/ceres/api/routes.py`:
```python
@router.post("/crawl/{agent_name}", status_code=202)
async def trigger_crawl(
    request: Request,
    agent_name: str,
    bank: Optional[str] = Query(None),
):
    runner = _get_runner(request)
    valid_agents = {"daily", "scout", "strategist", "crawler", "parser", "learning", "lab"}

    if agent_name not in valid_agents:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown agent: {agent_name}", "code": "UNKNOWN_AGENT"},
        )

    job = await runner.start_job(agent_name, bank_code=bank)

    if job is None:
        raise HTTPException(
            status_code=409,
            detail={"error": "A crawl is already running", "code": "CRAWL_ALREADY_RUNNING"},
        )

    return {
        "job_id": job.job_id,
        "agent": job.agent,
        "status": job.status,
        "started_at": job.started_at,
    }
```

- [ ] **Step 4: Run tests, verify pass**

```bash
poetry run pytest tests/test_api_routes.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/routes.py tests/test_api_routes.py
git commit -m "feat: add crawl trigger endpoints with concurrency gate (409 on conflict)"
```

---

## Phase 2: React Dashboard

### Task 6: Scaffold React App

**Files:**
- Create: `dashboard/` (entire React project scaffold)

- [ ] **Step 1: Create Vite React TypeScript project**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install @tanstack/react-query react-router-dom recharts
npm install lucide-react clsx tailwind-merge
```

- [ ] **Step 2: Configure Tailwind**

Update `dashboard/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
})
```

Update `dashboard/src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 3: Create API client**

`dashboard/src/api/client.ts`:
```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(error.error || resp.statusText);
  }
  return resp.json();
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}
```

- [ ] **Step 4: Create WebSocket hook**

`dashboard/src/hooks/useWebSocket.ts`:
```typescript
import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace('http', 'ws');

export interface CrawlEvent {
  event: string;
  job_id: string;
  agent?: string;
  message?: string;
  status?: string;
  error?: string;
  result?: Record<string, unknown>;
  ts: string;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<CrawlEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/ws/crawl-status`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ subscribe: 'all' }));
    };

    ws.onmessage = (event) => {
      const data: CrawlEvent = JSON.parse(event.data);
      setLastEvent(data);

      if (data.event === 'crawl_finished' || data.event === 'crawl_error') {
        queryClient.invalidateQueries();
      }
    };

    ws.onclose = () => setIsConnected(false);

    return () => ws.close();
  }, [queryClient]);

  return { lastEvent, isConnected };
}
```

- [ ] **Step 5: Create useCrawl hook**

`dashboard/src/hooks/useCrawl.ts`:
```typescript
import { useState } from 'react';
import { apiPost } from '../api/client';

interface CrawlResponse {
  job_id: string;
  agent: string;
  status: string;
  started_at: string;
}

export function useCrawl() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const triggerCrawl = async (agent: string, bank?: string) => {
    setError(null);
    setIsRunning(true);
    try {
      const params = bank ? `?bank=${bank}` : '';
      await apiPost<CrawlResponse>(`/api/crawl/${agent}${params}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger crawl');
      setIsRunning(false);
    }
  };

  const reset = () => {
    setIsRunning(false);
    setError(null);
  };

  return { triggerCrawl, isRunning, error, reset };
}
```

- [ ] **Step 6: Create App shell with routing**

`dashboard/src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Banks from './pages/Banks';
import BankDetail from './pages/BankDetail';
import LoanPrograms from './pages/LoanPrograms';
import CrawlLogs from './pages/CrawlLogs';
import Strategies from './pages/Strategies';
import Recommendations from './pages/Recommendations';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/banks" element={<Banks />} />
            <Route path="/banks/:id" element={<BankDetail />} />
            <Route path="/programs" element={<LoanPrograms />} />
            <Route path="/logs" element={<CrawlLogs />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/recommendations" element={<Recommendations />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 7: Create Layout component**

`dashboard/src/components/Layout.tsx`:
```tsx
import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/banks', label: 'Banks', icon: '🏦' },
  { path: '/programs', label: 'Loan Programs', icon: '💰' },
  { path: '/logs', label: 'Crawl Logs', icon: '📋' },
  { path: '/strategies', label: 'Strategies', icon: '🎯' },
  { path: '/recommendations', label: 'Recommendations', icon: '💡' },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { lastEvent, isConnected } = useWebSocket();

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b">
          <h1 className="text-xl font-bold text-gray-900">CERES</h1>
          <p className="text-sm text-gray-500">Ops Dashboard</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map(({ path, label, icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span>{icon}</span>
              {label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t">
          <div className={`flex items-center gap-2 text-xs ${isConnected ? 'text-green-600' : 'text-red-500'}`}>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
          {lastEvent && lastEvent.event !== 'subscribed' && (
            <p className="text-xs text-gray-400 mt-1 truncate">
              {lastEvent.agent}: {lastEvent.message || lastEvent.event}
            </p>
          )}
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 8: Create stub pages**

Create each page file with a minimal placeholder. Example for `dashboard/src/pages/Overview.tsx`:
```tsx
export default function Overview() {
  return <div><h2 className="text-2xl font-bold">Overview</h2><p>Loading...</p></div>;
}
```

Create similarly for: `Banks.tsx`, `BankDetail.tsx`, `LoanPrograms.tsx`, `CrawlLogs.tsx`, `Strategies.tsx`, `Recommendations.tsx`.

- [ ] **Step 9: Verify it builds and runs**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard
npm run build
```

- [ ] **Step 10: Commit**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
git add dashboard/
git commit -m "feat: scaffold React dashboard with routing, API client, WebSocket hook, and layout"
```

---

### Task 7: Overview Page

**Files:**
- Modify: `dashboard/src/pages/Overview.tsx`
- Create: `dashboard/src/components/StatsCard.tsx`
- Create: `dashboard/src/components/CrawlButton.tsx`

- [ ] **Step 1: Create StatsCard component**

`dashboard/src/components/StatsCard.tsx`:
```tsx
interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray';
}

const COLOR_MAP = {
  blue: 'bg-blue-50 text-blue-700',
  green: 'bg-green-50 text-green-700',
  red: 'bg-red-50 text-red-700',
  yellow: 'bg-yellow-50 text-yellow-700',
  gray: 'bg-gray-50 text-gray-700',
};

export default function StatsCard({ title, value, subtitle, color = 'blue' }: StatsCardProps) {
  return (
    <div className={`rounded-xl p-6 ${COLOR_MAP[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-sm mt-1 opacity-60">{subtitle}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create CrawlButton component**

`dashboard/src/components/CrawlButton.tsx`:
```tsx
import { useCrawl } from '../hooks/useCrawl';

interface CrawlButtonProps {
  agent: string;
  label: string;
  bank?: string;
  variant?: 'primary' | 'secondary';
}

export default function CrawlButton({ agent, label, bank, variant = 'primary' }: CrawlButtonProps) {
  const { triggerCrawl, isRunning, error } = useCrawl();

  const baseStyles = 'px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50';
  const styles = variant === 'primary'
    ? `${baseStyles} bg-blue-600 text-white hover:bg-blue-700`
    : `${baseStyles} bg-gray-100 text-gray-700 hover:bg-gray-200`;

  return (
    <div>
      <button
        onClick={() => triggerCrawl(agent, bank)}
        disabled={isRunning}
        className={styles}
      >
        {isRunning ? 'Running...' : label}
      </button>
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 3: Implement Overview page**

`dashboard/src/pages/Overview.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import StatsCard from '../components/StatsCard';
import CrawlButton from '../components/CrawlButton';

interface DashboardData {
  total_banks: number;
  banks_active: number;
  banks_unreachable: number;
  banks_blocked: number;
  total_programs: number;
  success_rate: number;
  total_crawls_7d: number;
  failures_7d: number;
}

export default function Overview() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardData>('/api/dashboard'),
  });

  if (isLoading || !data) return <p>Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <div className="flex gap-3">
          <CrawlButton agent="daily" label="Crawl All Banks" />
          <CrawlButton agent="scout" label="Run Scout" variant="secondary" />
          <CrawlButton agent="learning" label="Run Learning" variant="secondary" />
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatsCard title="Total Banks" value={data.total_banks} subtitle={`${data.banks_active} active`} color="blue" />
        <StatsCard title="Loan Programs" value={data.total_programs} color="green" />
        <StatsCard title="Success Rate (7d)" value={`${Math.round(data.success_rate * 100)}%`} color={data.success_rate >= 0.7 ? 'green' : 'red'} />
        <StatsCard title="Crawls (7d)" value={data.total_crawls_7d} subtitle={`${data.failures_7d} failed`} color="gray" />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
git add dashboard/src/
git commit -m "feat: add Overview page with stats cards and crawl action buttons"
```

---

### Task 8: Banks + Bank Detail Pages

**Files:**
- Modify: `dashboard/src/pages/Banks.tsx`
- Modify: `dashboard/src/pages/BankDetail.tsx`
- Create: `dashboard/src/components/StatusBadge.tsx`
- Create: `dashboard/src/components/DataTable.tsx`

- [ ] **Step 1: Create StatusBadge component**

`dashboard/src/components/StatusBadge.tsx`:
```tsx
const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  unreachable: 'bg-red-100 text-red-800',
  blocked: 'bg-yellow-100 text-yellow-800',
  unknown: 'bg-gray-100 text-gray-600',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  running: 'bg-blue-100 text-blue-800',
  partial: 'bg-yellow-100 text-yellow-800',
  timeout: 'bg-orange-100 text-orange-800',
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.unknown}`}>
      {status}
    </span>
  );
}
```

- [ ] **Step 2: Implement Banks page**

`dashboard/src/pages/Banks.tsx` — Table of all banks with category filter, click-to-detail, per-bank crawl button. Use `useQuery` with `['banks', page, category]` query key. Show paginated table with bank_code, name, category, website_status badge, last_crawled_at, programs_count.

- [ ] **Step 3: Implement BankDetail page**

`dashboard/src/pages/BankDetail.tsx` — Uses `useParams()` to get bank ID. Fetches `/api/banks/:id`. Shows bank info card, strategy summary, loan programs table, crawl log history, "Crawl This Bank" button.

- [ ] **Step 4: Verify build**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
git add dashboard/src/
git commit -m "feat: add Banks list and Bank Detail pages with status badges"
```

---

### Task 9: Loan Programs + Crawl Logs Pages

**Files:**
- Modify: `dashboard/src/pages/LoanPrograms.tsx`
- Modify: `dashboard/src/pages/CrawlLogs.tsx`

- [ ] **Step 1: Implement LoanPrograms page**

`dashboard/src/pages/LoanPrograms.tsx` — Paginated table with filters (bank, loan_type dropdown, sort selector). Columns: program_name, bank_code, loan_type, interest_rate range, amount range, tenure, confidence bar, completeness_score. Click row to expand and show `raw_data` JSON viewer.

- [ ] **Step 2: Implement CrawlLogs page**

`dashboard/src/pages/CrawlLogs.tsx` — Paginated table with status filter dropdown. Columns: timestamp (relative), bank_code, status badge, duration_ms formatted, programs_found, error_message truncated. Color-coded rows by status.

- [ ] **Step 3: Verify build**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
git add dashboard/src/
git commit -m "feat: add Loan Programs browser and Crawl Logs viewer with filtering"
```

---

### Task 10: Strategies + Recommendations Pages

**Files:**
- Modify: `dashboard/src/pages/Strategies.tsx`
- Modify: `dashboard/src/pages/Recommendations.tsx`

- [ ] **Step 1: Implement Strategies page**

`dashboard/src/pages/Strategies.tsx` — Table: bank_code, bypass_method, anti_bot_type, success_rate (progress bar), version, updated_at. Two action buttons per row: "Rebuild Strategy" (triggers `POST /api/crawl/strategist?bank=CODE`) and "Test with Lab" (triggers `POST /api/crawl/lab?bank=CODE`).

- [ ] **Step 2: Implement Recommendations page**

`dashboard/src/pages/Recommendations.tsx` — Card layout. Each card: rec_type badge, title, summary, priority star rating, impact_score bar, related banks listed. Group by rec_type. Read-only display.

- [ ] **Step 3: Verify build**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
git add dashboard/src/
git commit -m "feat: add Strategies management and Recommendations pages"
```

---

## Phase 3: Docker

### Task 11: Dockerfiles + Docker Compose

**Files:**
- Create: `Dockerfile` (API)
- Create: `dashboard/Dockerfile` (React)
- Create: `docker-compose.yml`

- [ ] **Step 1: Create API Dockerfile**

`Dockerfile`:
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY . .

RUN playwright install chromium

EXPOSE 8000
CMD ["uvicorn", "ceres.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create Dashboard Dockerfile**

`dashboard/Dockerfile`:
```dockerfile
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

`dashboard/nginx.conf`:
```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Create docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    command: uvicorn ceres.api:app --host 0.0.0.0 --port 8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/status"]
      interval: 10s
      retries: 3

  dashboard:
    build:
      context: ./dashboard
      args:
        VITE_API_URL: http://localhost:8000
    ports: ["3000:3000"]
    depends_on:
      api:
        condition: service_healthy
```

- [ ] **Step 4: Add dashboard/ to .gitignore node_modules**

Add to `.gitignore`:
```
dashboard/node_modules/
dashboard/dist/
```

- [ ] **Step 5: Test docker-compose build**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
docker-compose build
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile dashboard/Dockerfile dashboard/nginx.conf docker-compose.yml .gitignore
git commit -m "feat: add Docker Compose with API and dashboard containers"
```

---

### Task 12: Integration Verification

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
poetry run pytest tests/ -v --tb=short
```

- [ ] **Step 2: Start docker-compose and verify**

```bash
docker-compose up -d
# Wait for health check
sleep 15
# Test API
curl http://localhost:8000/api/status
curl http://localhost:8000/api/dashboard
# Test Dashboard
curl -s http://localhost:3000 | head -5
# Stop
docker-compose down
```

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "chore: verify docker-compose integration"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1: Backend API | 1-5 | FastAPI app, task runner, WebSocket, REST routes (read + write) |
| 2: React Dashboard | 6-10 | Scaffold, Overview, Banks, Programs, Logs, Strategies, Recommendations |
| 3: Docker | 11-12 | Dockerfiles, docker-compose, integration verification |

Total: **12 tasks**, ~30 new files, ~2500 lines of code

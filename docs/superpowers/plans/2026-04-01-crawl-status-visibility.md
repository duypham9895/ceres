# Crawl Status Visibility — Full Pipeline Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global, persistent crawl pipeline monitor to the CERES dashboard sidebar so the operator never needs to alt-tab to Docker logs.

**Architecture:** React Context (`CrawlStatusProvider`) wraps the app and consumes WebSocket events to maintain global crawl state. A `CrawlPipelineMonitor` component renders in the sidebar on every page. Backend enriches progress broadcasts with step index and bank counts, and enriches `/api/status` for mid-crawl hydration. Toast notifications via `sonner` on completion/failure.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, sonner (toasts), FastAPI, asyncpg

**Design doc:** `~/.gstack/projects/ceres/edwardpham-master-design-20260401-152852.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `dashboard/src/context/CrawlStatusContext.tsx` | React Context + Provider. Holds global crawl state, consumes WebSocket events, hydrates from `/api/status` on mount. Single source of truth. |
| `dashboard/src/components/CrawlPipelineMonitor.tsx` | Sidebar UI. Vertical stepper showing pipeline steps with status icons, bank counts, elapsed timer, failure counter, idle state. |
| `dashboard/src/components/CrawlToast.tsx` | Toast wrapper. Fires sonner toasts on `job_finish`/`job_error` with summary + link to logs. |

### Modified files
| File | Changes |
|------|---------|
| `src/ceres/api/tasks.py` | Add `_current_step`/`_step_index`/`_total_steps` tracking. Move `job_progress` broadcast to after step completion with bank counts. Add `job_step_start` broadcast when step begins. |
| `src/ceres/api/routes.py` | Enrich `/api/status` with `current_step`, `step_index`, `total_steps`, and `last_completed` (time-window aggregation from crawl_logs). |
| `dashboard/src/hooks/useWebSocket.ts` | Fix event name matching (`job_finish`/`job_error` instead of `crawl_finished`/`crawl_error`). Expose raw event stream for context consumption. |
| `dashboard/src/hooks/useCrawl.ts` | Remove local `isRunning` state. Consume `CrawlStatusContext` for global `isRunning`. Keep `triggerCrawl` and `error` handling. |
| `dashboard/src/components/CrawlButton.tsx` | Consume context for disabled state. Add tooltip when disabled. |
| `dashboard/src/components/Layout.tsx` | Mount `CrawlPipelineMonitor` in sidebar between nav and connection indicator. Remove old lastEvent display. |
| `dashboard/src/App.tsx` | Wrap app with `CrawlStatusProvider`. Add `<Toaster />` from sonner. |

### Test files
| File | What it tests |
|------|--------------|
| `tests/test_api_tasks.py` | (modify) Add tests for step tracking, enriched progress broadcasts |
| `tests/test_api_routes.py` | (modify) Add tests for enriched `/api/status` with `last_completed` |

---

## Task 1: Backend — Add step tracking to CrawlTaskRunner

**Files:**
- Modify: `src/ceres/api/tasks.py`
- Test: `tests/test_api_tasks.py`

- [ ] **Step 1: Write failing test for step tracking**

```python
# In tests/test_api_tasks.py, add to TestCrawlTaskRunner:

@pytest.mark.asyncio
async def test_step_tracking_during_daily(self):
    """CrawlTaskRunner tracks current step index during daily pipeline."""
    db = AsyncMock()
    runner = CrawlTaskRunner(db=db)
    broadcasts = []
    runner.set_broadcast_callback(AsyncMock(side_effect=lambda msg: broadcasts.append(msg)))

    # Mock the private runner methods directly (not _agent_registry, since
    # _run_daily calls self._run_scout etc., not the registry)
    async def fast_stub(**kw):
        return {"banks_processed": 5, "banks_total": 5, "banks_failed": 0}

    runner._run_scout = fast_stub
    runner._run_strategist = fast_stub
    runner._run_crawler = fast_stub
    runner._run_parser = fast_stub

    await runner.start_job("daily")
    await asyncio.sleep(0.3)  # Let pipeline complete

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
    """get_current_job returns step tracking when daily pipeline is running."""
    db = AsyncMock()
    runner = CrawlTaskRunner(db=db)
    step_reached = asyncio.Event()

    async def slow_scout(**kw):
        step_reached.set()
        await asyncio.sleep(10)
        return {"banks_processed": 0, "banks_total": 0, "banks_failed": 0}

    runner._run_scout = slow_scout  # Mock the method directly, not the registry

    await runner.start_job("daily")
    await step_reached.wait()

    current = runner.get_current_job()
    assert current is not None
    assert runner.get_step_info() == {"current_step": "scout", "step_index": 0, "total_steps": 4}
    await runner.cancel_all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_tasks.py -v -x`
Expected: FAIL — `get_step_info` does not exist, progress messages missing new fields

- [ ] **Step 3: Implement step tracking in CrawlTaskRunner**

In `src/ceres/api/tasks.py`:

1. Add three new instance fields in `__init__`:
```python
self._current_step: Optional[str] = None
self._step_index: int = 0
self._total_steps: int = 0
```

2. Add `get_step_info()` method:
```python
def get_step_info(self) -> Optional[dict]:
    """Return current pipeline step tracking info, or None if not a pipeline run."""
    if self._total_steps == 0:
        return None
    return {
        "current_step": self._current_step,
        "step_index": self._step_index,
        "total_steps": self._total_steps,
    }
```

3. Modify `_run_daily` — move broadcast to AFTER step completion, add step fields, broadcast a `job_step_start` before each step:
```python
async def _run_daily(self, **kwargs: Any) -> dict:
    job_id = self._current_job.job_id if self._current_job else ""
    results: Dict[str, Any] = {}

    steps = [
        ("scout", self._run_scout),
        ("strategist", self._run_strategist),
        ("crawler", self._run_crawler),
        ("parser", self._run_parser),
    ]
    self._total_steps = len(steps)

    for i, (step_name, step_fn) in enumerate(steps):
        self._current_step = step_name
        self._step_index = i

        await self._broadcast({
            "type": "job_step_start",
            "job_id": job_id,
            "agent": "daily",
            "step": step_name,
            "step_index": i,
            "total_steps": len(steps),
        })

        step_result = await step_fn(**kwargs)
        results[step_name] = step_result

        await self._broadcast({
            "type": "job_progress",
            "job_id": job_id,
            "agent": "daily",
            "step": step_name,
            "step_index": i,
            "total_steps": len(steps),
            "banks_processed": step_result.get("banks_processed", 0),
            "banks_total": step_result.get("banks_total", 0),
            "banks_failed": step_result.get("banks_failed", 0),
        })

    self._current_step = None
    self._step_index = 0
    self._total_steps = 0
    return results
```

4. Clear step tracking in `_execute` finally block:
```python
finally:
    self._current_job = None
    self._current_task = None
    self._current_step = None
    self._step_index = 0
    self._total_steps = 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_tasks.py -v -x`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/tasks.py tests/test_api_tasks.py
git commit -m "feat: add pipeline step tracking to CrawlTaskRunner"
```

---

## Task 1.5: Backend — Normalize agent return contracts for bank counts

The `_run_daily` pipeline reads `banks_processed`, `banks_total`, `banks_failed` from each agent's result dict. Currently, agents return different shapes (e.g., scout returns `{"banks_checked": N, "active": N, ...}`, crawler returns different keys). We need to normalize the runner methods to translate each agent's result into the standard fields.

**Files:**
- Modify: `src/ceres/api/tasks.py` (the `_run_*` wrapper methods)

- [ ] **Step 1: Update each `_run_*` method to normalize return values**

Add a helper that wraps the agent result with standardized fields. Modify each `_run_*` method in `tasks.py` to add `banks_processed`, `banks_total`, `banks_failed` to the returned dict based on what the agent actually returns:

```python
# Add after _broadcast method in CrawlTaskRunner:

@staticmethod
def _normalize_result(result: dict, agent_name: str) -> dict:
    """Add standardized bank count fields to agent results without mutation."""
    if "banks_processed" in result:
        return result  # Already normalized

    if agent_name == "scout":
        return {
            **result,
            "banks_processed": result.get("banks_checked", 0),
            "banks_total": result.get("banks_checked", 0),
            "banks_failed": result.get("unreachable", 0) + result.get("blocked", 0),
        }
    if agent_name == "crawler":
        return {
            **result,
            "banks_processed": result.get("banks_crawled", 0),
            "banks_total": result.get("banks_total", 0),
            "banks_failed": result.get("banks_failed", 0),
        }
    if agent_name == "parser":
        return {
            **result,
            "banks_processed": result.get("programs_parsed", 0),
            "banks_total": result.get("programs_parsed", 0) + len(result.get("errors", [])),
            "banks_failed": len(result.get("errors", [])),
        }
    # Default: no bank counts available
    return {**result, "banks_processed": 0, "banks_total": 0, "banks_failed": 0}
```

Then update `_run_daily` to normalize each step result:
```python
# In _run_daily, after step_result = await step_fn(**kwargs):
step_result = self._normalize_result(step_result, step_name)
results[step_name] = step_result
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_tasks.py -v -x`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/ceres/api/tasks.py
git commit -m "feat: normalize agent results with standard bank count fields"
```

---

## Task 2: Backend — Enrich /api/status endpoint

**Files:**
- Modify: `src/ceres/api/routes.py`
- Test: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing test for enriched /api/status**

```python
# In tests/test_api_routes.py, add:

class TestStatusRoute:
    @pytest.mark.asyncio
    async def test_status_includes_step_info_when_running(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        runner = MagicMock()
        job = MagicMock()
        job.job_id = "test-123"
        job.agent = "daily"
        job.status = MagicMock(value="running")
        job.started_at = "2026-04-01T12:00:00Z"
        runner.get_current_job.return_value = job
        runner.get_step_info.return_value = {
            "current_step": "crawler",
            "step_index": 2,
            "total_steps": 4,
        }
        app = make_test_app(db, mock_runner=runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
        data = resp.json()
        assert data["current_job"]["current_step"] == "crawler"
        assert data["current_job"]["step_index"] == 2
        assert data["current_job"]["total_steps"] == 4

    @pytest.mark.asyncio
    async def test_status_includes_last_completed_when_idle(self):
        db = AsyncMock()
        db.pool = AsyncMock()
        db.pool.fetchrow = AsyncMock(return_value={
            "finished_at": "2026-04-01T11:30:00Z",
            "success_count": 54,
            "total_count": 58,
        })
        runner = MagicMock()
        runner.get_current_job.return_value = None
        runner.get_step_info.return_value = None
        app = make_test_app(db, mock_runner=runner)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
        data = resp.json()
        assert data["current_job"] is None
        assert data["last_completed"]["success_count"] == 54
        assert data["last_completed"]["total_count"] == 58
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_routes.py::TestStatusRoute -v -x`
Expected: FAIL — `TestStatusRoute` class not found or missing fields

- [ ] **Step 3: Implement enriched /api/status**

Replace the `health_check` function in `src/ceres/api/routes.py`:

```python
@router.get("/status")
async def health_check(request: Request) -> dict:
    """Return service health status with current crawl job and last completed info."""
    runner = getattr(request.app.state, "task_runner", None)
    db = request.app.state.db
    current_job = runner.get_current_job() if runner else None
    step_info = runner.get_step_info() if runner else None

    current_job_data = None
    if current_job is not None:
        current_job_data = {
            "job_id": current_job.job_id,
            "agent": current_job.agent,
            "status": current_job.status.value if hasattr(current_job.status, 'value') else str(current_job.status),
            "started_at": current_job.started_at,
        }
        if step_info is not None:
            current_job_data = {**current_job_data, **step_info}

    # Fetch last completed crawl summary (time-window aggregation)
    last_completed = None
    if current_job is None:
        row = await db.pool.fetchrow("""
            WITH latest AS (
                SELECT created_at FROM crawl_logs ORDER BY created_at DESC LIMIT 1
            )
            SELECT
                MAX(cl.created_at) AS finished_at,
                COUNT(*) FILTER (WHERE cl.status = 'SUCCESS') AS success_count,
                COUNT(*) AS total_count
            FROM crawl_logs cl
            WHERE cl.created_at >= (SELECT created_at - INTERVAL '30 minutes' FROM latest)
        """)
        if row is not None and row["total_count"] is not None and row["total_count"] > 0:
            last_completed = {
                "finished_at": row["finished_at"],
                "success_count": row["success_count"],
                "total_count": row["total_count"],
            }

    return {
        "status": "ok",
        "current_job": current_job_data,
        "last_completed": last_completed,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/test_api_routes.py -v -x`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/api/routes.py tests/test_api_routes.py
git commit -m "feat: enrich /api/status with step tracking and last_completed"
```

---

## Task 3: Frontend — Install sonner and create CrawlStatusContext

**Files:**
- Create: `dashboard/src/context/CrawlStatusContext.tsx`
- Modify: `dashboard/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Install sonner**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm install sonner`

- [ ] **Step 2: Fix event names in useWebSocket.ts**

Replace `useWebSocket.ts` content. Key changes: match backend event types (`job_finish`/`job_error` instead of `crawl_finished`/`crawl_error`), add auto-reconnect on disconnect, expose `lastEvent` for the context to consume:

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws');

export interface CrawlEvent {
  type: string;
  job_id: string;
  agent?: string;
  step?: string;
  step_index?: number;
  total_steps?: number;
  banks_processed?: number;
  banks_total?: number;
  banks_failed?: number;
  error?: string;
  result?: Record<string, unknown>;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<CrawlEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${WS_URL}/ws/crawl-status`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      ws.send(JSON.stringify({ subscribe: 'all' }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as CrawlEvent;
      if (data.type) {
        setLastEvent(data);
      }
      if (data.type === 'job_finish' || data.type === 'job_error') {
        queryClient.invalidateQueries();
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      // Auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000);
    };
  }, [queryClient]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { lastEvent, isConnected };
}
```

- [ ] **Step 3: Create CrawlStatusContext.tsx**

Create `dashboard/src/context/CrawlStatusContext.tsx`:

```typescript
import { createContext, useContext, useEffect, useState, useRef, type ReactNode } from 'react';
import { useWebSocket, type CrawlEvent } from '../hooks/useWebSocket';
import { apiFetch } from '../api/client';

// --- Types ---

export interface PipelineStep {
  name: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  bankCount: number | null;
  bankTotal: number | null;
}

export interface LastCompletedCrawl {
  finishedAt: string;
  successCount: number;
  totalCount: number;
}

export interface CrawlStatus {
  isRunning: boolean;
  jobId: string | null;
  agent: string | null;
  currentStep: string | null;
  steps: PipelineStep[];
  startedAt: string | null;
  failures: number;
  lastCompletedCrawl: LastCompletedCrawl | null;
  isConnected: boolean;
}

const DAILY_STEPS = ['scout', 'strategist', 'crawler', 'parser'];

function buildPipelineSteps(agent: string): PipelineStep[] {
  if (agent === 'daily') {
    return DAILY_STEPS.map((name) => ({
      name,
      status: 'pending' as const,
      bankCount: null,
      bankTotal: null,
    }));
  }
  // Single-agent crawl: one step
  return [{ name: agent, status: 'pending', bankCount: null, bankTotal: null }];
}

const INITIAL_STATUS: CrawlStatus = {
  isRunning: false,
  jobId: null,
  agent: null,
  currentStep: null,
  steps: [],
  startedAt: null,
  failures: 0,
  lastCompletedCrawl: null,
  isConnected: false,
};

// --- Context ---

const CrawlStatusContext = createContext<CrawlStatus>(INITIAL_STATUS);

export function useCrawlStatus(): CrawlStatus {
  return useContext(CrawlStatusContext);
}

// --- Provider ---

interface StatusResponse {
  status: string;
  current_job: {
    job_id: string;
    agent: string;
    status: string;
    started_at: string;
    current_step?: string;
    step_index?: number;
    total_steps?: number;
  } | null;
  last_completed: {
    finished_at: string;
    success_count: number;
    total_count: number;
  } | null;
}

export function CrawlStatusProvider({ children }: { children: ReactNode }) {
  const { lastEvent, isConnected } = useWebSocket();
  const [status, setStatus] = useState<CrawlStatus>(INITIAL_STATUS);
  const hydrated = useRef(false);

  // Hydrate from /api/status on mount (handles browser refresh mid-crawl)
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;

    apiFetch<StatusResponse>('/api/status').then((data) => {
      if (data.current_job) {
        const job = data.current_job;
        const steps = buildPipelineSteps(job.agent);

        // Mark completed steps based on step_index
        const stepIndex = job.step_index ?? 0;
        const updatedSteps = steps.map((s, i) => {
          if (i < stepIndex) return { ...s, status: 'done' as const };
          if (i === stepIndex) return { ...s, status: 'running' as const };
          return s;
        });

        setStatus({
          isRunning: true,
          jobId: job.job_id,
          agent: job.agent,
          currentStep: job.current_step ?? steps[stepIndex]?.name ?? null,
          steps: updatedSteps,
          startedAt: job.started_at,
          failures: 0,
          lastCompletedCrawl: null,
          isConnected,
        });
      } else if (data.last_completed) {
        setStatus((prev) => ({
          ...prev,
          lastCompletedCrawl: {
            finishedAt: data.last_completed!.finished_at,
            successCount: data.last_completed!.success_count,
            totalCount: data.last_completed!.total_count,
          },
          isConnected,
        }));
      }
    }).catch(() => {
      // API unavailable — stay in initial state
    });
  }, [isConnected]);

  // Process WebSocket events
  useEffect(() => {
    if (!lastEvent) return;

    setStatus((prev) => processEvent(prev, lastEvent));
  }, [lastEvent]);

  // Keep isConnected in sync
  useEffect(() => {
    setStatus((prev) => prev.isConnected === isConnected ? prev : { ...prev, isConnected });
  }, [isConnected]);

  return (
    <CrawlStatusContext.Provider value={status}>
      {children}
    </CrawlStatusContext.Provider>
  );
}

// --- Event processor (pure function, no mutations) ---

function processEvent(prev: CrawlStatus, event: CrawlEvent): CrawlStatus {
  switch (event.type) {
    case 'job_start': {
      const steps = buildPipelineSteps(event.agent ?? 'daily');
      return {
        ...prev,
        isRunning: true,
        jobId: event.job_id,
        agent: event.agent ?? null,
        currentStep: steps[0]?.name ?? null,
        steps,
        startedAt: new Date().toISOString(),
        failures: 0,
        lastCompletedCrawl: null,
      };
    }

    case 'job_step_start': {
      const stepIndex = event.step_index ?? 0;
      const updatedSteps = prev.steps.map((s, i) => {
        if (i < stepIndex) return s.status === 'done' ? s : { ...s, status: 'done' as const };
        if (i === stepIndex) return { ...s, status: 'running' as const };
        return s;
      });
      return {
        ...prev,
        currentStep: event.step ?? null,
        steps: updatedSteps,
      };
    }

    case 'job_progress': {
      const stepIndex = event.step_index ?? 0;
      const banksFailed = event.banks_failed ?? 0;
      const updatedSteps = prev.steps.map((s, i) => {
        if (i === stepIndex) {
          return {
            ...s,
            status: 'done' as const,
            bankCount: event.banks_processed ?? null,
            bankTotal: event.banks_total ?? null,
          };
        }
        // Mark next step as running if it exists
        if (i === stepIndex + 1 && i < prev.steps.length) {
          return { ...s, status: 'running' as const };
        }
        return s;
      });
      return {
        ...prev,
        steps: updatedSteps,
        failures: prev.failures + banksFailed,
      };
    }

    case 'job_finish': {
      const finishedSteps = prev.steps.map((s) =>
        s.status !== 'done' ? { ...s, status: 'done' as const } : s
      );
      return {
        ...prev,
        isRunning: false,
        currentStep: null,
        steps: finishedSteps,
      };
    }

    case 'job_error': {
      const errorSteps = prev.steps.map((s) => {
        if (s.status === 'running') return { ...s, status: 'failed' as const };
        if (s.status === 'pending') return { ...s, status: 'skipped' as const };
        return s;
      });
      return {
        ...prev,
        isRunning: false,
        currentStep: null,
        steps: errorSteps,
      };
    }

    default:
      return prev;
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/hooks/useWebSocket.ts dashboard/src/context/CrawlStatusContext.tsx dashboard/package.json dashboard/package-lock.json
git commit -m "feat: add CrawlStatusContext with WebSocket event processing and hydration"
```

---

## Task 4: Frontend — Create CrawlPipelineMonitor component

**Files:**
- Create: `dashboard/src/components/CrawlPipelineMonitor.tsx`

- [ ] **Step 1: Create CrawlPipelineMonitor.tsx**

```typescript
import { useEffect, useState } from 'react';
import { useCrawlStatus, type PipelineStep } from '../context/CrawlStatusContext';

function formatElapsed(startedAt: string): string {
  const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}

function formatTimeAgo(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function StepIcon({ status }: { status: PipelineStep['status'] }) {
  switch (status) {
    case 'done':
      return <span className="text-green-500 transition-opacity duration-200">&#10003;</span>;
    case 'running':
      return <span className="text-blue-500 animate-pulse">&#9654;</span>;
    case 'failed':
      return <span className="text-red-500">&#10007;</span>;
    case 'skipped':
      return <span className="text-gray-300">&#9675;</span>;
    default:
      return <span className="text-gray-300">&#9675;</span>;
  }
}

function StepRow({ step }: { step: PipelineStep }) {
  const bankLabel = step.bankCount !== null && step.bankTotal !== null
    ? `${step.bankCount}/${step.bankTotal}`
    : step.status === 'running' ? '...' : '\u2014';

  return (
    <div className={`flex items-center justify-between py-1 text-sm ${
      step.status === 'running' ? 'text-blue-700 font-medium' :
      step.status === 'done' ? 'text-gray-700' :
      step.status === 'failed' ? 'text-red-600' :
      'text-gray-400'
    }`}>
      <div className="flex items-center gap-2">
        <StepIcon status={step.status} />
        <span className="capitalize">{step.name}</span>
      </div>
      <span className="text-xs tabular-nums">{bankLabel}</span>
    </div>
  );
}

export default function CrawlPipelineMonitor() {
  const status = useCrawlStatus();
  const [elapsed, setElapsed] = useState('');

  // Update timer every second when running
  useEffect(() => {
    if (!status.isRunning || !status.startedAt) {
      setElapsed('');
      return;
    }
    setElapsed(formatElapsed(status.startedAt));
    const interval = setInterval(() => {
      setElapsed(formatElapsed(status.startedAt!));
    }, 1000);
    return () => clearInterval(interval);
  }, [status.isRunning, status.startedAt]);

  // Idle state
  if (!status.isRunning && status.steps.length === 0) {
    return (
      <div className="px-4 py-3 border-t border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="w-2 h-2 rounded-full bg-gray-300" />
          Ready
        </div>
        {status.lastCompletedCrawl && (
          <p className="text-xs text-gray-400 mt-1">
            Last crawl: {formatTimeAgo(status.lastCompletedCrawl.finishedAt)} —{' '}
            {status.lastCompletedCrawl.successCount}/{status.lastCompletedCrawl.totalCount} OK
          </p>
        )}
      </div>
    );
  }

  // Running or just-completed state (steps still visible after completion)
  return (
    <div className="px-4 py-3 border-t border-b border-gray-100 bg-blue-50/50">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-900">
          {status.isRunning ? 'Crawl in Progress' : 'Crawl Complete'}
        </span>
        {elapsed && (
          <span className="text-xs text-gray-500 tabular-nums">{elapsed}</span>
        )}
      </div>

      <div className="space-y-0.5">
        {status.steps.map((step) => (
          <StepRow key={step.name} step={step} />
        ))}
      </div>

      {status.failures > 0 && (
        <p className="text-xs text-orange-600 mt-2">
          {status.failures} failure{status.failures !== 1 ? 's' : ''} so far
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/CrawlPipelineMonitor.tsx
git commit -m "feat: add CrawlPipelineMonitor sidebar component"
```

---

## Task 5: Frontend — Create CrawlToast component

**Files:**
- Create: `dashboard/src/components/CrawlToast.tsx`

- [ ] **Step 1: Create CrawlToast.tsx**

```typescript
import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useCrawlStatus } from '../context/CrawlStatusContext';

export default function CrawlToast() {
  const status = useCrawlStatus();
  const navigate = useNavigate();
  const prevRunning = useRef(status.isRunning);

  useEffect(() => {
    // Fire toast when crawl transitions from running to not-running
    if (prevRunning.current && !status.isRunning && status.steps.length > 0) {
      const hasFailed = status.steps.some((s) => s.status === 'failed');
      const doneSteps = status.steps.filter((s) => s.status === 'done');
      const totalBanks = doneSteps.reduce((sum, s) => sum + (s.bankTotal ?? 0), 0);
      const successBanks = doneSteps.reduce((sum, s) => sum + (s.bankCount ?? 0), 0) - status.failures;

      if (hasFailed) {
        toast.error('Crawl Failed', {
          description: `Failed at ${status.steps.find((s) => s.status === 'failed')?.name ?? 'unknown'} step`,
          action: {
            label: 'View Logs',
            onClick: () => navigate('/logs'),
          },
          duration: 8000,
        });
      } else {
        toast.success('Crawl Complete', {
          description: totalBanks > 0
            ? `${successBanks}/${totalBanks} banks OK${status.failures > 0 ? ` \u2022 ${status.failures} failures` : ''}`
            : 'All steps completed',
          action: status.failures > 0
            ? { label: 'View Logs', onClick: () => navigate('/logs') }
            : undefined,
          duration: 8000,
        });
      }
    }
    prevRunning.current = status.isRunning;
  }, [status.isRunning, status.steps, status.failures, navigate]);

  return null; // Toasts are rendered by <Toaster /> in App.tsx
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/CrawlToast.tsx
git commit -m "feat: add CrawlToast for completion/failure notifications"
```

---

## Task 6: Frontend — Refactor CrawlButton and useCrawl to use global state

**Files:**
- Modify: `dashboard/src/hooks/useCrawl.ts`
- Modify: `dashboard/src/components/CrawlButton.tsx`

- [ ] **Step 1: Refactor useCrawl.ts**

Replace the file. Remove local `isRunning` state, consume `CrawlStatusContext` instead:

```typescript
import { useState } from 'react';
import { apiPost } from '../api/client';
import { useCrawlStatus } from '../context/CrawlStatusContext';

interface CrawlResponse {
  job_id: string;
  agent: string;
  status: string;
  started_at: string;
}

export function useCrawl() {
  const { isRunning } = useCrawlStatus();
  const [error, setError] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

  const triggerCrawl = async (agent: string, bank?: string) => {
    setError(null);
    setIsTriggering(true);
    try {
      const params = bank ? `?bank=${bank}` : '';
      await apiPost<CrawlResponse>(`/api/crawl/${agent}${params}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger crawl');
    } finally {
      setIsTriggering(false);
    }
  };

  const reset = () => setError(null);

  return { triggerCrawl, isRunning, isTriggering, error, reset };
}
```

- [ ] **Step 2: Refactor CrawlButton.tsx**

Replace the file. Consume context for disabled state, add tooltip, show spinner while triggering:

```typescript
import { useCrawl } from '../hooks/useCrawl';

interface CrawlButtonProps {
  agent: string;
  label: string;
  bank?: string;
  variant?: 'primary' | 'secondary';
}

export default function CrawlButton({ agent, label, bank, variant = 'primary' }: CrawlButtonProps) {
  const { triggerCrawl, isRunning, isTriggering, error } = useCrawl();
  const disabled = isRunning || isTriggering;

  const baseStyles = 'px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
  const styles = variant === 'primary'
    ? `${baseStyles} bg-blue-600 text-white hover:bg-blue-700`
    : `${baseStyles} bg-gray-100 text-gray-700 hover:bg-gray-200`;

  return (
    <div className="relative group">
      <button
        onClick={() => triggerCrawl(agent, bank)}
        disabled={disabled}
        className={styles}
      >
        {isTriggering ? 'Starting...' : label}
      </button>
      {isRunning && !isTriggering && (
        <span className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          A crawl is already running
        </span>
      )}
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/hooks/useCrawl.ts dashboard/src/components/CrawlButton.tsx
git commit -m "refactor: CrawlButton and useCrawl consume global CrawlStatusContext"
```

---

## Task 7: Frontend — Wire everything in Layout and App

**Files:**
- Modify: `dashboard/src/components/Layout.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Update Layout.tsx**

Replace the file. Mount `CrawlPipelineMonitor` in sidebar, mount `CrawlToast`, keep connection indicator but remove old lastEvent text:

```typescript
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useCrawlStatus } from '../context/CrawlStatusContext';
import CrawlPipelineMonitor from './CrawlPipelineMonitor';
import CrawlToast from './CrawlToast';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: '\ud83d\udcca' },
  { path: '/banks', label: 'Banks', icon: '\ud83c\udfe6' },
  { path: '/programs', label: 'Loan Programs', icon: '\ud83d\udcb0' },
  { path: '/logs', label: 'Crawl Logs', icon: '\ud83d\udccb' },
  { path: '/strategies', label: 'Strategies', icon: '\ud83c\udfaf' },
  { path: '/recommendations', label: 'Recommendations', icon: '\ud83d\udca1' },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isConnected } = useCrawlStatus();

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b">
          <h1 className="text-xl font-bold text-gray-900">CERES</h1>
          <p className="text-sm text-gray-500">Ops Dashboard</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map(({ path, label, icon }) => (
            <Link key={path} to={path}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm ${
                location.pathname === path
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}>
              <span>{icon}</span>{label}
            </Link>
          ))}
        </nav>
        <CrawlPipelineMonitor />
        <div className="p-4 border-t">
          <div className={`flex items-center gap-2 text-xs ${isConnected ? 'text-green-600' : 'text-red-500'}`}>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            {isConnected ? 'Connected' : 'Reconnecting...'}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">{children}</main>
      <CrawlToast />
    </div>
  );
}
```

- [ ] **Step 2: Update App.tsx**

Wrap the app with `CrawlStatusProvider` and add `<Toaster />`:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { CrawlStatusProvider } from './context/CrawlStatusContext';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Banks from './pages/Banks';
import BankDetail from './pages/BankDetail';
import LoanPrograms from './pages/LoanPrograms';
import CrawlLogs from './pages/CrawlLogs';
import Strategies from './pages/Strategies';
import Recommendations from './pages/Recommendations';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <CrawlStatusProvider>
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
          <Toaster position="top-right" richColors />
        </CrawlStatusProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/Layout.tsx dashboard/src/App.tsx
git commit -m "feat: wire CrawlStatusProvider, PipelineMonitor, and Toaster into app"
```

---

## Task 7.5: Frontend — Unit tests for processEvent state machine

The `processEvent` function in `CrawlStatusContext.tsx` is the core state machine. It's a pure function that takes previous state + event and returns new state. This must be tested for every event type.

**Files:**
- Create: `dashboard/src/context/__tests__/processEvent.test.ts`

- [ ] **Step 1: Set up test infrastructure (if not already present)**

Check if vitest is installed. If not:
Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npm install -D vitest`

- [ ] **Step 2: Export `processEvent` and `buildPipelineSteps` from CrawlStatusContext**

Add named exports for the two pure functions at the bottom of `CrawlStatusContext.tsx`:
```typescript
// Export for testing
export { processEvent, buildPipelineSteps };
```

- [ ] **Step 3: Write tests**

Create `dashboard/src/context/__tests__/processEvent.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { processEvent, buildPipelineSteps } from '../CrawlStatusContext';
import type { CrawlStatus } from '../CrawlStatusContext';
import type { CrawlEvent } from '../../hooks/useWebSocket';

const INITIAL: CrawlStatus = {
  isRunning: false,
  jobId: null,
  agent: null,
  currentStep: null,
  steps: [],
  startedAt: null,
  failures: 0,
  lastCompletedCrawl: null,
  isConnected: true,
};

describe('buildPipelineSteps', () => {
  it('builds 4 steps for daily agent', () => {
    const steps = buildPipelineSteps('daily');
    expect(steps).toHaveLength(4);
    expect(steps.map(s => s.name)).toEqual(['scout', 'strategist', 'crawler', 'parser']);
    expect(steps.every(s => s.status === 'pending')).toBe(true);
  });

  it('builds 1 step for single agent', () => {
    const steps = buildPipelineSteps('scout');
    expect(steps).toHaveLength(1);
    expect(steps[0].name).toBe('scout');
  });
});

describe('processEvent', () => {
  it('job_start initializes pipeline', () => {
    const event: CrawlEvent = { type: 'job_start', job_id: '123', agent: 'daily' };
    const result = processEvent(INITIAL, event);
    expect(result.isRunning).toBe(true);
    expect(result.jobId).toBe('123');
    expect(result.steps).toHaveLength(4);
    expect(result.currentStep).toBe('scout');
  });

  it('job_step_start marks current step as running', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const event: CrawlEvent = { type: 'job_step_start', job_id: '1', step: 'strategist', step_index: 1, total_steps: 4 };
    const result = processEvent(running, event);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[1].status).toBe('running');
    expect(result.currentStep).toBe('strategist');
  });

  it('job_progress marks step as done with bank counts', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const stepped = processEvent(running, { type: 'job_step_start', job_id: '1', step: 'scout', step_index: 0, total_steps: 4 });
    const event: CrawlEvent = { type: 'job_progress', job_id: '1', step: 'scout', step_index: 0, total_steps: 4, banks_processed: 55, banks_total: 58, banks_failed: 3 };
    const result = processEvent(stepped, event);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[0].bankCount).toBe(55);
    expect(result.steps[0].bankTotal).toBe(58);
    expect(result.failures).toBe(3);
  });

  it('job_finish marks all steps done', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const event: CrawlEvent = { type: 'job_finish', job_id: '1', agent: 'daily' };
    const result = processEvent(running, event);
    expect(result.isRunning).toBe(false);
    expect(result.steps.every(s => s.status === 'done')).toBe(true);
  });

  it('job_error marks running step as failed, pending as skipped', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    // Set step 2 (crawler) as running
    const stepped = processEvent(running, { type: 'job_step_start', job_id: '1', step: 'crawler', step_index: 2, total_steps: 4 });
    const event: CrawlEvent = { type: 'job_error', job_id: '1', agent: 'daily', error: 'timeout' };
    const result = processEvent(stepped, event);
    expect(result.isRunning).toBe(false);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[1].status).toBe('done');
    expect(result.steps[2].status).toBe('failed');
    expect(result.steps[3].status).toBe('skipped');
  });

  it('single agent job_start creates one step', () => {
    const event: CrawlEvent = { type: 'job_start', job_id: '1', agent: 'scout' };
    const result = processEvent(INITIAL, event);
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].name).toBe('scout');
  });

  it('unknown event type returns state unchanged', () => {
    const event: CrawlEvent = { type: 'unknown_event', job_id: '1' };
    const result = processEvent(INITIAL, event);
    expect(result).toBe(INITIAL);
  });
});
```

- [ ] **Step 4: Run frontend tests**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npx vitest run src/context/__tests__/processEvent.test.ts`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/context/__tests__/processEvent.test.ts dashboard/src/context/CrawlStatusContext.tsx
git commit -m "test: add unit tests for processEvent state machine"
```

---

## Task 8: Verification — All tests pass and build succeeds

**Files:**
- None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build check**

Run: `cd /Users/edwardpham/Documents/Programming/Projects/ceres/dashboard && npx tsc --noEmit && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Final commit if any fixes needed**

Only commit if fixes were required in steps 1-2.

# TODOS

## 1. Fix bank_code missing from /api/loan-programs response
**What:** The `/api/loan-programs` endpoint does `SELECT * FROM loan_programs` which doesn't include `bank_code` (it's on the `banks` table). LoanPrograms.tsx renders `program.bank_code` which is undefined.
**Why:** Users see an empty Bank column in the Loan Programs page.
**Fix:** Add `JOIN banks b ON b.id = lp.bank_id` to the loan-programs query and include `b.bank_code` in the SELECT.
**Depends on:** Nothing. Can be fixed independently.

## 2. Add error boundaries and loading skeletons for dashboard components
**What:** The new hand-built components (RateHeatmap, LiveFeed, SparklineChart, RingChart, TimelineEvent) have no error boundaries or loading skeleton states.
**Why:** If the heatmap API is slow or the WebSocket disconnects, users see a blank page or a crash instead of graceful degradation.
**Fix:** Add a React error boundary wrapper and skeleton loading states (shimmer placeholders) for each new component.
**Depends on:** Phase 1 of the redesign (components must exist first).

## 3. WebSocket burst handling for full crawl events
**What:** During a full 58-bank crawl, the WebSocket will fire ~58 events in rapid succession. The LiveFeed component re-renders on each event. With CSS fade animations running simultaneously, this may cause visible jank.
**Why:** The live feed is the main real-time feature. Jank during the most active moment (full crawl) would be the worst time to look broken.
**Fix:** Batch WebSocket events with a 100ms throttle (accumulate events, flush to state on requestAnimationFrame). Only matters if jank is observed in practice.
**Depends on:** Phase 1 of the redesign (LiveFeed must exist first).

## 4. Add per-step error handling in _run_daily pipeline
**What:** `_run_daily()` in `tasks.py:246-275` runs pipeline steps sequentially with no try/except around individual steps. If scout throws, strategist/crawler/parser never run and the whole pipeline aborts.
**Why:** One failing agent shouldn't block the rest. If scout fails but strategist has cached strategies, the crawler can still work with existing data.
**Fix:** Wrap each `step_fn(**kwargs)` call in try/except. On failure, record the error in the results dict and continue to the next step. Return accumulated results with per-step success/failure status.
**Pros:** More resilient pipeline, better step-level error reporting in agent_runs result JSONB.
**Cons:** Running downstream agents with missing upstream data could produce incomplete or garbage output. Needs careful thought about which failures should actually halt the pipeline.
**Depends on:** Nothing. Can be done independently.

## 5. Add API header auto-refresh for discovered bank API endpoints
**What:** When a discovered API endpoint starts returning 401/403 (expired session/CSRF token), automatically clear the stale `api_headers` and re-run API discovery to get fresh headers, rather than falling back to browser every time.
**Why:** Static `api_headers` in `bank_strategies` will rot as tokens expire. The fallback to browser works (api_endpoint overlay pattern), but every crawl wastes time trying a dead API first.
**Fix:** In `_fetch_via_api()`, detect 401/403 responses. On auth failure, null out `api_headers` in the strategy and optionally queue a re-discovery via LabAgent.
**Depends on:** API discovery implementation (anti-bot bypass sprint).

## 6. Add browser process pooling to BrowserManager
**What:** Reuse browser instances across page fetches instead of launching/killing a new browser per page. Pool warm browsers per BrowserType, hand out pages from existing contexts.
**Why:** Current `_fetch_page()` creates `BrowserManager()` → `create_context()` → fetch → `close_context()` per URL. With 58 banks and Semaphore(5), that's hundreds of browser launches per crawl. Each Camoufox launch is ~3-5 seconds.
**Fix:** Add a `BrowserPool` that maintains a pool of browser instances per type, bounded by max_concurrency. `get_page()` returns a page from an existing browser or launches a new one if under limit. `release_page()` returns the page to the pool.
**Depends on:** Browser adapter pattern (anti-bot bypass sprint).

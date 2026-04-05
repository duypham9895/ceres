# Ceres Refactoring Plan

## Root Cause Diagnosis

The app can't crawl valid loan programs because of **cascading failures across every layer**:

### Why Crawling Produces No Valid Data
1. **Strategist always writes `selectors: {}`** — selector-based extraction is permanently disabled
2. **LLMExtractor never injected** in production — the best extraction path is dead code
3. **undetected-chromedriver `page_source`** passes a string as callable → `TypeError` → empty HTML
4. **Anti-bot HTML stored as valid** — blocked pages get parsed as if they contain loan data
5. **Partial success = "failed"** — `CrawlStatus.PARTIAL` exists but is never used
6. **Only 4 of 12 loan types** recognized — 8 types map to "OTHER"
7. **120-char name cap** silently drops valid Indonesian product names
8. **No SPA wait strategy** — `networkidle` doesn't wait for JS-rendered content
9. **No proxy rotation** — `NoOpProxyProvider` is the only implementation
10. **No captcha solving** — captcha pages stored and parsed as loan data

### Why Job Management Is Broken
1. **No job status endpoint** — once dispatched, jobs are a black box
2. **arq jobs don't write to `agent_runs`** — DB has no record of distributed jobs
3. **`max_tries = 1`** — zero retries, ever. `config.max_retries = 3` is never read
4. **No scheduling/cron** — arq supports it natively but it's not configured
5. **No job cancellation API** — `cancel_all()` exists but no HTTP endpoint
6. **`daily` forced in-process** — blocks API event loop for up to 600 seconds
7. **Dual ID system** — `job_id` UUID is never indexed or queryable

### Why Dashboard Can't Manage Operations
1. **Global crawl lock** — any running job disables ALL crawl buttons everywhere
2. **`quality_avg` type mismatch** — KPI always shows 0%
3. **Recommendations summary hardcoded to zeros**
4. **Bulk rebuild ignores selection** — always calls rebuild-all
5. **Client-side sort on paginated data** — misleading results
6. **No job queue panel, no cancel button, no schedule view**

---

## Execution Phases

### Phase 1: Fix Crawling Pipeline (CRITICAL)
*Goal: Make the crawler actually produce valid loan program data*

- [ ] P1.1: Strategist — implement real selector discovery using LLM analysis of page HTML
- [ ] P1.2: Parser — auto-inject LLMExtractor when API keys are available
- [ ] P1.3: Crawler — fix undetected-chromedriver `page_source` (property, not callable)
- [ ] P1.4: Crawler — skip storing anti-bot HTML, mark crawl as BLOCKED
- [ ] P1.5: Crawler — use CrawlStatus.PARTIAL for mixed success/failure
- [ ] P1.6: Normalizer — add patterns for all 12 loan types
- [ ] P1.7: Parser — raise name length cap from 120 to 300 chars
- [ ] P1.8: Crawler — add `page.wait_for_selector` for SPA content
- [ ] P1.9: Models — fix field name mismatch (tenor vs tenure)

### Phase 2: Fix Job Queue System (CRITICAL)
*Goal: Make jobs observable, retriable, and schedulable*

- [ ] P2.1: Queue — use `config.max_retries` in arq `WorkerSettings.max_tries`
- [ ] P2.2: Queue — write `agent_runs` records from arq worker path
- [ ] P2.3: API — add `GET /api/jobs/{job_id}` status endpoint
- [ ] P2.4: API — add `POST /api/jobs/{job_id}/cancel` endpoint
- [ ] P2.5: API — add `GET /api/queue/status` (depth, running, failed)
- [ ] P2.6: Tasks — remove `daily` from `_inprocess_agents`, run via arq
- [ ] P2.7: Queue — add arq `cron_jobs` for daily scheduled crawl
- [ ] P2.8: Database — add `job_id` column to `agent_runs`
- [ ] P2.9: Database — wrap `upsert_loan_program` in transaction

### Phase 3: Fix Data Quality (HIGH)
*Goal: Only store and serve valid, complete loan data*

- [ ] P3.1: Database — add minimum confidence threshold (0.4) at storage boundary
- [ ] P3.2: Database — add rate sanity bounds (0.1% - 30%)
- [ ] P3.3: Database — add min/max cross-validation (min <= max)
- [ ] P3.4: Schema — fix case mismatch (uppercase Python enum vs lowercase DB CHECK)
- [ ] P3.5: Schema — add unique partial index on `(bank_id, program_name, loan_type) WHERE is_latest`

### Phase 4: Fix Dashboard (HIGH)
*Goal: Proper ops dashboard for managing crawl operations*

- [ ] P4.1: Remove global crawl lock — allow per-bank operations during pipeline run
- [ ] P4.2: Fix `quality_avg` type mismatch in Overview KPI
- [ ] P4.3: Fix Recommendations summary strip (compute real counts)
- [ ] P4.4: Fix Strategies bulk rebuild to send selected banks
- [ ] P4.5: Add Jobs page — queue visibility, status, cancel buttons
- [ ] P4.6: Add error boundaries and proper error handling

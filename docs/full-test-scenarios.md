# Full Test Scenarios

This file defines the standard verification workflow for CERES. It is the
source-controlled checklist for validating that crawler, parser, API,
dashboard, and Docker changes still work well after code changes.

The code-level scenario manifest lives in:

- `src/ceres/verification.py`

## Standard Command

Code-only verification:

```bash
poetry run ceres verify
```

Full local verification including Docker smoke checks:

```bash
poetry run ceres verify --docker
```

Stricter release verification:

```bash
poetry run ceres verify-release
poetry run ceres verify-release --bank BCA
```

`--docker` is a feature smoke run, not only a status check.

## Automated Scenarios

### 1. Backend correctness

Command:

```bash
pytest -q
```

Covers:
- Agent behavior
- Parser extraction and normalization
- API routes and filters
- Queue/task orchestration
- Browser manager lifecycle
- Regression tests for recent engineering fixes

Pass condition:
- Entire backend suite passes

### 2. Frontend correctness

Command:

```bash
cd dashboard && npx vitest run
```

Covers:
- Filter state behavior
- Crawl status event processing
- Shared components
- Dashboard page logic covered by frontend unit tests

Pass condition:
- Entire frontend unit test suite passes

### 3. Frontend production build

Command:

```bash
cd dashboard && npm run build
```

Covers:
- TypeScript compilation
- Vite production bundling
- Asset/build-time integration issues

Pass condition:
- Production bundle completes successfully

### 4. Docker rebuild and runtime smoke

Command:

```bash
poetry run ceres verify --docker
```

Covers:
- `docker compose build`
- `docker compose up -d`
- `docker compose ps`
- feature API smoke suite against:
  - `/api/status`
  - `/api/dashboard`
  - `/api/banks`
  - `/api/banks/:id`
  - `/api/strategies`
  - `/api/loan-programs`
  - `/api/crawl-logs`
  - `/api/recommendations`
  - `/api/agent-runs/latest`
  - `/api/pipeline-health`
  - `/api/rates/heatmap`
  - `/api/rates/trend`
- worst-case API checks for:
  - invalid loan rate range
  - invalid date format
  - nonexistent bank lookup
  - unknown crawl agent

Pass condition:
- Images rebuild successfully
- Compose services start successfully
- Core feature endpoints return valid payloads
- Invalid inputs fail with expected 4xx responses

## Happy / Worst Case Coverage

### Happy cases

- Backend and frontend regression suites pass.
- Dashboard/API read paths load successfully.
- Bank listing and bank detail responses are structurally valid.
- Loan programs, crawl logs, strategy, recommendation, and rate endpoints respond successfully.
- Dockerized app boots and exposes a healthy API.

### Worst cases

- Invalid loan rate filters return 400.
- Invalid date filter returns 400.
- Unknown bank lookup returns 404.
- Unknown crawl agent returns 400.
- Backend regression tests still cover deeper worst-case behaviors:
  - strategy rows missing `bank_code`
  - browser launch/cleanup edge cases
  - parser fallback paths
  - queue dedup and cancellation handling
  - pipeline-health/accounting regressions

## Required Release Scenarios

The following must be green before shipping changes:

1. Backend test suite
2. Frontend test suite
3. Frontend production build
4. Docker rebuild
5. Docker feature API smoke check
6. Database schema compatibility check
7. Single-bank live pipeline smoke for high-risk crawler/parser releases

## Release Verification

`poetry run ceres verify-release` adds stricter gates on top of `verify`:

- runs the full automated verification workflow
- checks the connected database for required tables/columns
- optionally runs a real single-bank strategist/crawler/parser/status smoke flow

Recommended usage:

```bash
poetry run ceres verify-release --bank BCA
```

Use `--bank` with a stable, known-good bank code in your environment.

## Manual / Operational Scenarios

These are important but not fully automated yet. They should be run for
high-risk crawler, parser, schema, or deployment changes.

### 1. Single-bank crawl smoke

Command example:

```bash
poetry run ceres crawler --bank BCA
poetry run ceres parser --bank BCA
poetry run ceres status --bank BCA
```

Verify:
- Crawl creates raw HTML rows
- Parser creates loan programs
- Bank status remains sane

### 2. All-bank stability run

Command example:

```bash
poetry run ceres crawler
poetry run ceres parser
```

Verify:
- No browser/process leak
- No orphaned `running` logs
- Parser drains backlog without repeatedly failing the same rows

### 3. Schema compatibility check

Verify before deploy:
- Production schema matches `database/schema.sql`
- New columns have been migrated before code depending on them is deployed

### 4. Metrics consistency check

Verify:
- `loan_programs` latest count matches dashboard/API expectations
- `crawl_logs.programs_found` reflects actual parsed output
- Pipeline status and dashboard summaries are coherent

## Known Gaps

Current verification does not fully automate:
- Live remote Postgres smoke validation
- End-to-end crawl of a real bank website in CI
- Duplicate-version churn detection across near-duplicate URLs
- Metrics consistency assertions against production data
- Dashboard browser E2E testing

These should be added as future smoke tests when the environment supports
stable remote/browser execution.

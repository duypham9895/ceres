# Dashboard Full Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign all 7 dashboard pages from passive data display to actionable intelligence — health bar, enriched KPI cards, tabbed Rate Intelligence, actionable alerts with CTAs, and enhanced pages for Banks, Loan Programs, Crawl Logs, Strategies, Recommendations, and Bank Detail.

**Architecture:** Backend-first approach — extend existing FastAPI endpoints and add 5 new GET endpoints + 1 PATCH endpoint, then rebuild React pages using shared components. Each page is independent and can be built in parallel after shared components are done.

**Tech Stack:** Python/FastAPI backend, React 19 + TypeScript + Tailwind CSS 4 + TanStack Query v5 + Recharts 3 + Radix UI + Lucide icons + Sonner toasts.

**Spec:** `docs/superpowers/specs/2026-04-03-dashboard-full-redesign.md`

---

## File Structure

### Backend — New/Modified Files
| File | Action | Responsibility |
|------|--------|---------------|
| `src/ceres/api/routes.py` | Modify | Add 5 new GET endpoints, 1 PATCH endpoint, extend 7 existing endpoints |
| `src/ceres/database.py` | Modify | Add query methods for alerts, changes, quality, analytics, compare |
| `database/migrations/001_add_status_note.sql` | Create | Add status_note column to ringkas_recommendations |

### Frontend — Shared Components (new)
| File | Responsibility |
|------|---------------|
| `dashboard/src/components/SummaryStrip.tsx` | Reusable colored status counts strip for all list pages |
| `dashboard/src/components/KpiCard.tsx` | KPI card with value, delta, sparkline — replaces StatsCard |
| `dashboard/src/components/SparklineBar.tsx` | Tiny bar chart for KPI cards and table cells |
| `dashboard/src/components/CompletenessBar.tsx` | Thin progress bar for data quality scores |
| `dashboard/src/components/ConfidenceDots.tsx` | 5-dot confidence indicator |
| `dashboard/src/components/TrendChip.tsx` | Colored trend badge (↑ 0.5%, ↓ 0.2%, → 0%) |
| `dashboard/src/components/AlertItem.tsx` | Alert row with icon, message, category, CTA button |
| `dashboard/src/components/HealthBar.tsx` | Thin top status bar for Overview page |

### Frontend — Page Rewrites
| File | Action | Scope |
|------|--------|-------|
| `dashboard/src/pages/Overview.tsx` | Rewrite | Full rewrite — zones layout |
| `dashboard/src/pages/Banks.tsx` | Modify | Add bulk actions, quality/health columns, sorting |
| `dashboard/src/pages/LoanPrograms.tsx` | Modify | Add compare mode, rate types, missing fields tooltip |
| `dashboard/src/pages/CrawlLogs.tsx` | Modify | Add analytics strip, error breakdown, CTAs on failed |
| `dashboard/src/pages/Strategies.tsx` | Modify | Add success sparkline, rebuild feedback |
| `dashboard/src/pages/Recommendations.tsx` | Modify | Add status workflow, actions, pagination |
| `dashboard/src/pages/BankDetail.tsx` | Modify | Add health/quality cards, CTAs on pipeline steps |

### Frontend — Types
| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard/src/types/dashboard.ts` | Create | TypeScript interfaces for all new API response shapes |

### Frontend — Removed
| File | Action |
|------|--------|
| `dashboard/src/components/LiveFeed.tsx` | Delete (after Overview rewrite) |
| `dashboard/src/components/RingChart.tsx` | Delete (after Overview rewrite) |
| `dashboard/src/components/RateHeatmap.tsx` | Delete (after Overview rewrite) |

---

## Phase 1: Backend Endpoints

### Task 1: Schema Migration — Add status_note column

**Files:**
- Create: `database/migrations/001_add_status_note.sql`
- Modify: `database/schema.sql` (add column to table definition)

- [ ] **Step 1: Create migration file**

```sql
-- database/migrations/001_add_status_note.sql
ALTER TABLE ringkas_recommendations ADD COLUMN IF NOT EXISTS status_note VARCHAR(500);
```

- [ ] **Step 2: Update schema.sql to include the column**

In `database/schema.sql`, add `status_note VARCHAR(500)` to the `ringkas_recommendations` table definition after the `status` column.

- [ ] **Step 3: Run migration against local DB**

```bash
docker compose exec postgres psql -U ceres -d ceres -f /docker-entrypoint-initdb.d/migrations/001_add_status_note.sql
```

- [ ] **Step 4: Commit**

```bash
git add database/migrations/001_add_status_note.sql database/schema.sql
git commit -m "feat: add status_note column to ringkas_recommendations"
```

---

### Task 2: Database Layer — New Query Methods

**Files:**
- Modify: `src/ceres/database.py`
- Test: `tests/test_database_dashboard.py` (create)

- [ ] **Step 1: Write failing tests for new query methods**

Create `tests/test_database_dashboard.py` with tests for:
- `get_dashboard_alerts()` — returns alerts grouped by category
- `get_dashboard_changes(date)` — returns today's changes
- `get_dashboard_quality()` — returns quality distribution
- `get_crawl_analytics(days=7)` — returns stats, error breakdown, daily trend
- `get_loan_compare(loan_type)` — returns programs for comparison
- `get_dashboard_extended()` — returns extended dashboard with sparklines

Each test should set up test data with the DB fixture, call the method, and assert the response shape. Example pattern:

```python
async def test_get_dashboard_alerts(db):
    # Insert a bank with website_status='unreachable' and last_crawled_at > 24h ago
    # Call db.get_dashboard_alerts()
    # Assert result contains alert with category='crawl_failure', type='unreachable'
    pass
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_database_dashboard.py -v
```

- [ ] **Step 3: Implement `get_dashboard_alerts()` in database.py**

Query logic:
1. **Crawl failures — unreachable**: `SELECT bank_code FROM banks WHERE website_status = 'unreachable' AND last_crawled_at < NOW() - INTERVAL '24 hours'`
2. **Crawl failures — anti-bot**: `SELECT b.bank_code FROM crawl_logs cl JOIN banks b ON cl.bank_id = b.id WHERE cl.status = 'blocked' AND cl.created_at > NOW() - INTERVAL '24 hours'`
3. **Rate anomalies**: Compare current `is_latest=true` loan_programs against previous version (`is_latest=false`) for same `(bank_id, loan_type, program_name)` where `ABS(current.min_interest_rate - prev.min_interest_rate) > 0.5`
4. **Data quality**: `SELECT b.bank_code FROM loan_programs lp JOIN banks b ON lp.bank_id = b.id WHERE lp.is_latest = true AND lp.completeness_score < 0.5`
5. **Stale data**: `SELECT bank_code FROM banks WHERE last_crawled_at < NOW() - INTERVAL '3 days' AND website_status = 'active'`
6. **Strategy health**: `SELECT b.bank_code FROM bank_strategies bs JOIN banks b ON bs.bank_id = b.id WHERE bs.is_active = true AND bs.success_rate < 0.3`

Return shape:
```python
[{"category": str, "type": str, "message": str, "count": int, "bank_codes": list[str], "cta": {"label": str, "agent": str}}]
```

- [ ] **Step 4: Implement `get_dashboard_changes(date)` in database.py**

Query logic:
1. **New programs**: `SELECT COUNT(*) FROM loan_programs WHERE is_latest = true AND DATE(created_at) = date`
2. **Rate changes**: Compare current vs previous version of loan_programs updated today, split by increase/decrease
3. **Status changes**: `SELECT COUNT(*) FROM banks WHERE DATE(updated_at) = date AND website_status != (previous status)` — approximate by checking crawl_logs status transitions

Return shape:
```python
[{"type": str, "count": int, "detail": str}]
```

- [ ] **Step 5: Implement `get_dashboard_quality()` in database.py**

```sql
SELECT
  COUNT(*) FILTER (WHERE avg_score > 0.8) AS high,
  COUNT(*) FILTER (WHERE avg_score BETWEEN 0.5 AND 0.8) AS medium,
  COUNT(*) FILTER (WHERE avg_score < 0.5) AS low,
  AVG(avg_score) AS avg_completeness
FROM (
  SELECT bank_id, AVG(completeness_score) AS avg_score
  FROM loan_programs WHERE is_latest = true
  GROUP BY bank_id
) sub
```

- [ ] **Step 6: Implement `get_crawl_analytics(days)` in database.py**

Extends existing `get_crawl_stats()` with:
- Error breakdown: `GROUP BY status` counts
- Daily success rate: `SELECT DATE(created_at), COUNT(*) FILTER (WHERE status = 'success') * 1.0 / COUNT(*) FROM crawl_logs WHERE created_at > NOW() - interval GROUP BY DATE(created_at) ORDER BY 1`

- [ ] **Step 7: Implement `get_loan_compare(loan_type)` in database.py**

```sql
SELECT b.bank_code, b.bank_name, lp.min_interest_rate, lp.max_interest_rate,
       lp.rate_fixed, lp.rate_floating, lp.rate_promo, lp.rate_promo_duration_months,
       lp.completeness_score
FROM loan_programs lp
JOIN banks b ON lp.bank_id = b.id
WHERE lp.is_latest = true AND lp.loan_type = $1
ORDER BY lp.min_interest_rate ASC NULLS LAST
```

- [ ] **Step 8: Implement extended dashboard sparklines**

Add to existing `get_dashboard_data()` or create `get_dashboard_sparklines(days=7)`:
```sql
-- Bank count by day (cumulative)
SELECT DATE(created_at), COUNT(*) FROM banks WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY 1 ORDER BY 1;
-- Program count by day
SELECT DATE(created_at), COUNT(*) FROM loan_programs WHERE is_latest = true AND created_at > NOW() - INTERVAL '7 days' GROUP BY 1 ORDER BY 1;
-- Avg KPR rate by day
SELECT DATE(updated_at), AVG(min_interest_rate) FROM loan_programs WHERE is_latest = true AND loan_type = 'KPR' AND updated_at > NOW() - INTERVAL '7 days' GROUP BY 1 ORDER BY 1;
-- Avg completeness by day
SELECT DATE(updated_at), AVG(completeness_score) FROM loan_programs WHERE is_latest = true AND updated_at > NOW() - INTERVAL '7 days' GROUP BY 1 ORDER BY 1;
```

- [ ] **Step 9: Run tests and verify they pass**

```bash
python -m pytest tests/test_database_dashboard.py -v
```

- [ ] **Step 10: Commit**

```bash
git add src/ceres/database.py tests/test_database_dashboard.py
git commit -m "feat: add dashboard query methods for alerts, changes, quality, analytics, compare"
```

---

### Task 3: API Routes — New Endpoints

**Files:**
- Modify: `src/ceres/api/routes.py`
- Test: `tests/test_api_dashboard.py` (create)

- [ ] **Step 1: Write failing tests for new endpoints**

Create `tests/test_api_dashboard.py` testing:
- `GET /api/dashboard/alerts` → returns `{"total": int, "alerts": [...]}`
- `GET /api/dashboard/changes` → returns `{"date": str, "changes": [...]}`
- `GET /api/dashboard/quality` → returns `{"high": {...}, "medium": {...}, "low": {...}, "avg_completeness": float}`
- `GET /api/crawl-logs/analytics` → returns `{"stats": {...}, "error_breakdown": {...}, "daily_success_rate": [...]}`
- `GET /api/loan-programs/compare?loan_type=KPR` → returns `{"loan_type": str, "programs": [...]}`
- `PATCH /api/recommendations/{id}` → returns updated recommendation

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_api_dashboard.py -v
```

- [ ] **Step 3: Implement GET /api/dashboard/alerts**

```python
@router.get("/dashboard/alerts")
async def dashboard_alerts(request: Request):
    db = request.app.state.db
    alerts = await db.get_dashboard_alerts()
    total = sum(a["count"] for a in alerts)
    return {"total": total, "alerts": alerts}
```

- [ ] **Step 4: Implement GET /api/dashboard/changes**

```python
@router.get("/dashboard/changes")
async def dashboard_changes(request: Request):
    from datetime import date
    db = request.app.state.db
    today = date.today()
    changes = await db.get_dashboard_changes(today)
    return {"date": today.isoformat(), "changes": changes}
```

- [ ] **Step 5: Implement GET /api/dashboard/quality**

```python
@router.get("/dashboard/quality")
async def dashboard_quality(request: Request):
    db = request.app.state.db
    return await db.get_dashboard_quality()
```

- [ ] **Step 6: Implement GET /api/crawl-logs/analytics**

```python
@router.get("/crawl-logs/analytics")
async def crawl_log_analytics(request: Request, days: int = Query(7, ge=1, le=90)):
    db = request.app.state.db
    return await db.get_crawl_analytics(days=days)
```

- [ ] **Step 7: Implement GET /api/loan-programs/compare**

```python
@router.get("/loan-programs/compare")
async def loan_programs_compare(request: Request, loan_type: str = Query(...)):
    db = request.app.state.db
    programs = await db.get_loan_compare(loan_type)
    return {"loan_type": loan_type, "programs": programs}
```

- [ ] **Step 8: Implement PATCH /api/recommendations/{id}**

```python
@router.patch("/recommendations/{rec_id}")
async def update_recommendation(request: Request, rec_id: UUID):
    body = await request.json()
    status = body.get("status")
    status_note = body.get("status_note")
    valid_statuses = {"pending", "reviewed", "in_progress", "done", "dismissed"}
    if status and status not in valid_statuses:
        return _error(f"Invalid status: {status}", code="INVALID_STATUS", status=400)
    db = request.app.state.db
    result = await db.update_recommendation(rec_id, status=status, status_note=status_note)
    if not result:
        return _error("Recommendation not found", code="NOT_FOUND", status=404)
    return result
```

- [ ] **Step 9: Extend existing GET /api/dashboard with sparklines and deltas**

Modify the existing `dashboard()` handler to include `quality_avg`, `deltas`, and `sparklines` in the response by calling the new query methods.

- [ ] **Step 10: Extend GET /api/rates/heatmap with completeness and confidence**

Modify the heatmap query to JOIN loan_programs and include `completeness_score`, `data_confidence`, and 7d trend per bank.

- [ ] **Step 11: Extend GET /api/banks with crawl_health and avg_quality**

Modify the banks list query to include:
- `crawl_streak` (already on banks table)
- `success_rate_30d` (from crawl_logs subquery)
- `avg_quality` (from loan_programs subquery)

- [ ] **Step 12: Extend GET /api/strategies with success_trend**

Add a subquery to include last 30 days of daily success rates as an array for sparkline display.

- [ ] **Step 13: Extend GET /api/recommendations with pagination and filtering**

Add `page`, `limit`, `status`, `sort` query params. Return paginated response using existing `_paginated()` helper.

- [ ] **Step 14: Extend GET /api/loan-programs with rate type breakdown**

Add `rate_fixed`, `rate_floating`, `rate_promo`, `rate_promo_duration_months` to the loan programs response.

- [ ] **Step 15: Run all tests**

```bash
python -m pytest tests/test_api_dashboard.py -v
python -m pytest tests/ -v --timeout=30
```

- [ ] **Step 16: Commit**

```bash
git add src/ceres/api/routes.py tests/test_api_dashboard.py
git commit -m "feat: add dashboard alerts, changes, quality, analytics, compare endpoints"
```

---

## Phase 2: Shared Frontend Components

### Task 4: TypeScript Interfaces

**Files:**
- Create: `dashboard/src/types/dashboard.ts`

- [ ] **Step 1: Create type definitions for all new API responses**

```typescript
// dashboard/src/types/dashboard.ts

export interface DashboardAlert {
  category: string;
  type: string;
  message: string;
  count: number;
  bank_codes: string[];
  cta: { label: string; agent: string };
}

export interface AlertsResponse {
  total: number;
  alerts: DashboardAlert[];
}

export interface DashboardChange {
  type: string;
  count: number;
  detail: string;
}

export interface ChangesResponse {
  date: string;
  changes: DashboardChange[];
}

export interface QualityResponse {
  high: { count: number; threshold: number };
  medium: { count: number; threshold: number };
  low: { count: number; threshold: number };
  avg_completeness: number;
}

export interface CrawlAnalytics {
  stats: {
    total_crawls_7d: number;
    success_rate: number;
    success_rate_prev_week: number;
    avg_duration_ms: number;
    programs_found: number;
    programs_new: number;
  };
  error_breakdown: Record<string, number>;
  daily_success_rate: Array<{ date: string; rate: number }>;
}

export interface CompareProgram {
  bank_code: string;
  bank_name: string;
  min_interest_rate: number | null;
  max_interest_rate: number | null;
  rate_fixed: number | null;
  rate_floating: number | null;
  rate_promo: number | null;
  rate_promo_duration_months: number | null;
  completeness_score: number;
}

export interface CompareResponse {
  loan_type: string;
  programs: CompareProgram[];
}

export interface ExtendedDashboard {
  total_banks: number;
  total_programs: number;
  banks_by_status: Record<string, number>;
  success_rate: number;
  crawl_stats: Record<string, number>;
  quality_avg: number;
  deltas: {
    banks_week: number;
    programs_new: number;
    kpr_rate_change: number;
    quality_change: number;
  };
  sparklines: {
    banks: number[];
    programs: number[];
    kpr_rate: number[];
    quality: number[];
  };
}

export interface HeatmapBank {
  bank_code: string;
  bank_name: string;
  website_status: string;
  rates: Record<string, number | null>;
  completeness_score: number;
  data_confidence: number;
  trend_7d: number | null;
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/types/dashboard.ts
git commit -m "feat: add TypeScript interfaces for dashboard redesign API responses"
```

---

### Task 5: Shared UI Components

**Files:**
- Create: `dashboard/src/components/SparklineBar.tsx`
- Create: `dashboard/src/components/CompletenessBar.tsx`
- Create: `dashboard/src/components/ConfidenceDots.tsx`
- Create: `dashboard/src/components/TrendChip.tsx`
- Create: `dashboard/src/components/KpiCard.tsx`
- Create: `dashboard/src/components/SummaryStrip.tsx`
- Create: `dashboard/src/components/AlertItem.tsx`
- Create: `dashboard/src/components/HealthBar.tsx`

- [ ] **Step 1: Create SparklineBar component**

Tiny bar chart — array of numbers rendered as vertical bars. Props: `data: number[]`, `color?: string`, `height?: number`. Use inline divs, not Recharts (too heavy for inline sparklines).

```tsx
// dashboard/src/components/SparklineBar.tsx
interface SparklineBarProps {
  readonly data: number[];
  readonly color?: string;
  readonly highlightLast?: boolean;
  readonly height?: number;
}
```

Render as flex row of divs with heights proportional to max value. Last bar gets `color` prop, others get muted version.

- [ ] **Step 2: Create CompletenessBar component**

```tsx
// dashboard/src/components/CompletenessBar.tsx
interface CompletenessBarProps {
  readonly score: number; // 0-1
  readonly width?: number; // px, default 60
}
```

Thin horizontal bar. Fill color: green >0.8, yellow 0.5-0.8, red <0.5.

- [ ] **Step 3: Create ConfidenceDots component**

```tsx
// dashboard/src/components/ConfidenceDots.tsx
interface ConfidenceDotsProps {
  readonly score: number; // 0-1, mapped to 1-5 dots
  readonly max?: number; // default 5
}
```

Row of 5 small circles. Filled dots = `Math.round(score * max)`. Filled = green, empty = gray.

- [ ] **Step 4: Create TrendChip component**

```tsx
// dashboard/src/components/TrendChip.tsx
interface TrendChipProps {
  readonly value: number; // positive = up, negative = down, 0 = flat
  readonly suffix?: string; // default "%"
}
```

Green chip with ↓ for negative (rate going down = good), red chip with ↑ for positive, gray with → for zero. Format: `↓ 0.3%`.

- [ ] **Step 5: Create KpiCard component**

```tsx
// dashboard/src/components/KpiCard.tsx
interface KpiCardProps {
  readonly title: string;
  readonly value: string | number;
  readonly delta?: string;
  readonly deltaDirection?: 'up' | 'down' | 'neutral';
  readonly sparkline?: number[];
  readonly sparklineColor?: string;
}
```

Card with title (muted uppercase), big value, delta text (colored by direction), SparklineBar at bottom. Uses existing Tailwind classes from StatsCard pattern: `bg-bg-card rounded-xl p-5 border border-border-light`.

- [ ] **Step 6: Create SummaryStrip component**

```tsx
// dashboard/src/components/SummaryStrip.tsx
interface SummaryStripItem {
  label: string;
  value: number;
  color: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}

interface SummaryStripProps {
  readonly items: SummaryStripItem[];
  readonly actions?: React.ReactNode; // slot for quick filter buttons
}
```

Horizontal bar with colored dots + labels. Pattern: `● 40 active · ● 13 unreachable · ● 5 blocked`.

- [ ] **Step 7: Create AlertItem component**

```tsx
// dashboard/src/components/AlertItem.tsx
interface AlertItemProps {
  readonly icon: string;
  readonly message: string;
  readonly category: string;
  readonly ctaLabel: string;
  readonly onAction: () => void;
  readonly loading?: boolean;
}
```

Row with icon, message + category subtitle, and CTA button on the right. CTA shows loading spinner when clicked.

- [ ] **Step 8: Create HealthBar component**

```tsx
// dashboard/src/components/HealthBar.tsx
interface HealthBarProps {
  readonly banksByStatus: Record<string, number>;
  readonly pipelineStep?: string;
  readonly pipelineProgress?: string;
  readonly successRate: number;
  readonly successRateTrend?: number;
}
```

Thin strip at page top. Three sections: left = bank status dots, center = pipeline progress (from CrawlStatusContext), right = success rate with trend.

- [ ] **Step 9: Add responsive variants to all components**

Apply responsive breakpoints from the spec:
- **KpiCard grid**: Use `grid-cols-2 lg:grid-cols-4` (4-col desktop, 2-col tablet, stacks on mobile via grid default)
- **HealthBar**: Use `flex-wrap` so sections wrap on mobile. Hide pipeline text on mobile (`hidden md:block`)
- **SummaryStrip**: Use `flex-wrap gap-2` so items wrap on small screens
- **Rate Intelligence table**: On mobile (<768px), hide Completeness and Confidence columns (`hidden md:table-cell`). On tablet, keep all columns.
- **Right sidebar grid**: Use `grid-cols-1 lg:grid-cols-[1fr_380px]` so sidebar stacks below on tablet/mobile

- [ ] **Step 10: Add loading skeleton and empty states**

Create `dashboard/src/components/Skeleton.tsx`:
```tsx
export function SkeletonCard() {
  return <div className="bg-bg-card rounded-xl p-5 border border-border-light animate-pulse h-28" />;
}
export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="bg-bg-card rounded-xl border border-border-light p-4 space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-4 bg-bg-hover rounded animate-pulse" />
      ))}
    </div>
  );
}
```

Add empty states per spec:
- **NeedsAttention**: When `alerts.total === 0`, show "All clear — no issues detected" with green checkmark icon
- **TodaysChanges**: When `changes.length === 0`, show "No changes yet today"
- **QualitySummary**: When all counts are 0, show "No quality data available"
- **CompareView**: When `programs.length === 0`, show "No {loan_type} programs found. Try a different loan type."
- **Recommendations**: Keep existing "No recommendations yet" with "Run Learning" button

Wrap each page section with loading check:
```tsx
{isLoading ? <SkeletonCard /> : <KpiCard ... />}
```

- [ ] **Step 11: Commit**

```bash
git add dashboard/src/components/SparklineBar.tsx dashboard/src/components/CompletenessBar.tsx dashboard/src/components/ConfidenceDots.tsx dashboard/src/components/TrendChip.tsx dashboard/src/components/KpiCard.tsx dashboard/src/components/SummaryStrip.tsx dashboard/src/components/AlertItem.tsx dashboard/src/components/HealthBar.tsx dashboard/src/components/Skeleton.tsx
git commit -m "feat: add shared dashboard components — KpiCard, SummaryStrip, AlertItem, HealthBar, SparklineBar, CompletenessBar, ConfidenceDots, TrendChip, Skeleton"
```

---

## Phase 3: Page Rewrites

### Task 6: Overview Page — Full Rewrite

**Files:**
- Rewrite: `dashboard/src/pages/Overview.tsx`
- Delete (after): `dashboard/src/components/LiveFeed.tsx`, `dashboard/src/components/RingChart.tsx`, `dashboard/src/components/RateHeatmap.tsx`

- [ ] **Step 1: Rewrite Overview.tsx with zone layout**

The page structure:
```tsx
<div>
  <HealthBar ... />                    {/* Zone 1 */}
  <div className="p-6 max-w-[1400px] mx-auto">
    <h1>Overview</h1>
    <div className="grid grid-cols-4 gap-3">  {/* Zone 2: KPI Cards */}
      <KpiCard title="Banks Monitored" ... />
      <KpiCard title="Loan Programs" ... />
      <KpiCard title="Avg KPR Rate" ... />
      <KpiCard title="Data Quality" ... />
    </div>
    <div className="grid grid-cols-[1fr_380px] gap-4 mt-5"> {/* Zone 3+4 */}
      <RateIntelligenceTable />         {/* Zone 3 */}
      <div className="space-y-3">       {/* Zone 4: Right sidebar */}
        <NeedsAttentionPanel />
        <TodaysChangesPanel />
        <QualitySummaryPanel />
      </div>
    </div>
  </div>
</div>
```

Use 5 queries:
```tsx
useQuery({ queryKey: ['dashboard'], queryFn: () => apiFetch<ExtendedDashboard>('/api/dashboard') });
useQuery({ queryKey: ['heatmap', activeTab], queryFn: () => apiFetch<HeatmapBank[]>(`/api/rates/heatmap?loan_type=${activeTab}`) });
useQuery({ queryKey: ['dashboard-alerts'], queryFn: () => apiFetch<AlertsResponse>('/api/dashboard/alerts') });
useQuery({ queryKey: ['dashboard-changes'], queryFn: () => apiFetch<ChangesResponse>('/api/dashboard/changes') });
useQuery({ queryKey: ['dashboard-quality'], queryFn: () => apiFetch<QualityResponse>('/api/dashboard/quality') });
```

- [ ] **Step 2: Implement Rate Intelligence Table section**

Inline in Overview.tsx (or extract if >150 lines). Features:
- Tab bar: KPR | KPA | Multiguna | Kendaraan | All (useState for activeTab)
- Table columns: Bank (with status dot), Min Rate, Max Rate, 7d Trend, Completeness, Confidence
- Rate color coding: `<6% text-success`, `6-8% text-warning`, `>8% text-error`
- Sortable columns using local state
- Click row → `navigate(/banks/${bank.id})`

- [ ] **Step 3: Implement Needs Attention panel**

Map alerts to AlertItem components. Each CTA calls `apiPost('/api/crawl/{agent}?bank={bank_code}')`. Show loading state on button during request. Use `useMutation` from TanStack Query. Show Sonner toast on success/failure.

- [ ] **Step 4: Implement Today's Changes panel**

Simple list of change items with colored badges (NEW=green, RATE=blue, ALERT=red).

- [ ] **Step 5: Implement Quality Summary panel**

Three horizontal bars with labels and bank counts. Use CompletenessBar component.

- [ ] **Step 6: Delete old components and their tests**

Remove `LiveFeed.tsx`, `RingChart.tsx`, `RateHeatmap.tsx` and their test files. Verify no other pages import them first:
```bash
cd dashboard && grep -r "LiveFeed\|RingChart\|RateHeatmap" src/pages/ --include="*.tsx"
```

- [ ] **Step 7: Verify Overview page loads correctly**

```bash
cd dashboard && npm run dev
```

Open http://localhost:3000/ and verify all zones render, data loads, CTAs work.

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/pages/Overview.tsx
git rm dashboard/src/components/LiveFeed.tsx dashboard/src/components/RingChart.tsx dashboard/src/components/RateHeatmap.tsx
git rm dashboard/src/components/__tests__/LiveFeed.test.tsx dashboard/src/components/__tests__/RingChart.test.tsx dashboard/src/components/__tests__/RateHeatmap.test.tsx 2>/dev/null || true
git commit -m "feat: rewrite Overview page — health bar, KPI cards, Rate Intelligence, actionable alerts"
```

---

### Task 7: Banks Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/Banks.tsx`

- [ ] **Step 1: Add SummaryStrip at top**

Query `/api/banks` already returns data with `banks_by_status`. Add `<SummaryStrip>` with items derived from the response.

- [ ] **Step 2: Add new columns to table**

Add columns: Crawl Health (streak + success bar), Data Quality (CompletenessBar), and enhance Actions column with both "Crawl" and "Re-learn" buttons. The backend should now return `crawl_streak`, `success_rate_30d`, `avg_quality` per bank.

- [ ] **Step 3: Add checkbox column for multi-select**

Follow existing Strategies.tsx pattern for checkboxes. Add state: `selectedBanks: Set<string>`.

- [ ] **Step 4: Add bulk actions bar**

When `selectedBanks.size > 0`, show bar with:
- "Crawl Selected (N)" → loops `apiPost('/api/crawl/crawler?bank=${code}')` for each
- "Re-learn Selected (N)" → loops `apiPost('/api/crawl/learning?bank=${code}')` for each
- "Clear" → clears selection

- [ ] **Step 5: Add column sorting**

Add `sortBy` and `sortDir` state. Click column header to toggle. Apply sort in query string or client-side.

- [ ] **Step 6: Verify and commit**

```bash
git add dashboard/src/pages/Banks.tsx
git commit -m "feat: enhance Banks page — summary strip, bulk actions, health/quality columns, sorting"
```

---

### Task 8: Loan Programs Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/LoanPrograms.tsx`

- [ ] **Step 1: Add SummaryStrip at top**

Show total programs, loan types count, avg completeness, low-quality count.

- [ ] **Step 2: Add Rate Type chips in table**

Display `rate_fixed`, `rate_floating`, `rate_promo` as colored chips in a new "Rate Type" column. Format: "Fixed 5.5%", "Floating 8.2%", "Promo 3.5% (12mo)".

- [ ] **Step 3: Add missing fields tooltip in expandable row**

Compute missing fields from the program data. Expected fields: `program_name, loan_type, min_interest_rate, max_interest_rate, min_amount, max_amount, min_tenor_months, max_tenor_months`. Show tooltip: "Missing: max_amount, min_tenor_months".

- [ ] **Step 4: Add Re-parse CTA on low-quality rows**

If `completeness_score < 0.5`, show "Re-parse" button in Actions column. Calls `apiPost('/api/crawl/parser?bank=${bank_code}')`.

- [ ] **Step 5: Add Compare View mode**

Add mode toggle (List/Compare) at top right. When Compare:
- Show loan type dropdown
- Fetch `/api/loan-programs/compare?loan_type=${selected}`
- Render comparison table: Bank, Min Rate, Max Rate, Fixed, Floating, Promo, Completeness
- Highlight lowest rate (green bg) and highest rate (red bg)

- [ ] **Step 6: Fix field name: tenure → tenor (full codebase)**

Search the entire frontend codebase for `tenure` and replace with `tenor` to match database schema:
```bash
cd dashboard && grep -r "tenure" src/ --include="*.ts" --include="*.tsx"
```
Replace all instances of `min_tenure_months`/`max_tenure_months` with `min_tenor_months`/`max_tenor_months` in every file found (pages, types, tests).

- [ ] **Step 7: Verify and commit**

```bash
git add dashboard/src/pages/LoanPrograms.tsx
git commit -m "feat: enhance Loan Programs — compare view, rate types, missing fields tooltip, re-parse CTA"
```

---

### Task 9: Crawl Logs Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/CrawlLogs.tsx`

- [ ] **Step 1: Add analytics strip with 4 mini KPI cards**

Fetch `/api/crawl-logs/analytics`. Show: Total Crawls (7d), Success Rate (with trend), Avg Duration, Programs Found.

- [ ] **Step 2: Add error breakdown bar**

Horizontal stacked bar showing Success/Failed/Blocked/Timeout proportions. Use inline divs with flex, not Recharts. Color-coded. Clickable to filter timeline.

- [ ] **Step 3: Add success rate trend chart**

Use Recharts `LineChart` (already a dependency) to plot daily success rate over 30 days. Add a red reference line at 70%.

- [ ] **Step 4: Add CTAs on failed/blocked timeline entries**

For entries with `status === 'failed'`, add "Re-crawl" button → `apiPost('/api/crawl/crawler?bank=${bank_code}')`.
For entries with `status === 'blocked'`, add "Retry" button → `apiPost('/api/crawl/crawler?bank=${bank_code}&force=true')`.

- [ ] **Step 5: Verify and commit**

```bash
git add dashboard/src/pages/CrawlLogs.tsx
git commit -m "feat: enhance Crawl Logs — analytics strip, error breakdown, trend chart, re-crawl CTAs"
```

---

### Task 10: Strategies Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/Strategies.tsx`

- [ ] **Step 1: Add SummaryStrip at top**

Show: X healthy, Y degraded, Z dead, W% avg success rate. Derive from existing data.

- [ ] **Step 2: Add success trend sparkline column**

Add SparklineBar in a new "Trend" column showing 30-day success rate trend (from extended API response).

- [ ] **Step 3: Improve rebuild feedback**

After bulk rebuild, show per-bank status. The `/api/strategies/rebuild-all` response includes `queued` and `failed` arrays. Display each bank's status in a toast or inline feedback panel: green for queued, red for failed with error message.

- [ ] **Step 4: Verify and commit**

```bash
git add dashboard/src/pages/Strategies.tsx
git commit -m "feat: enhance Strategies — summary strip, success sparklines, rebuild feedback"
```

---

### Task 11: Recommendations Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/Recommendations.tsx`

- [ ] **Step 1: Add SummaryStrip with filter tabs**

Strip shows: X total, Y action required, Z new this week. Add filter tabs: All | Action Required | New | Reviewed | Dismissed. Pass `?status=` to API query.

- [ ] **Step 2: Add pagination**

The extended endpoint now supports `?page=&limit=`. Add pagination controls matching existing pattern from Banks/LoanPrograms pages.

- [ ] **Step 3: Replace card grid with priority-sorted list**

Each recommendation becomes a list row with: priority stars, type chip, title, summary, impact bar, created date, status badge, action buttons.

- [ ] **Step 4: Add action buttons (Act / Dismiss)**

- "Act" → `PATCH /api/recommendations/{id}` with `{ status: "in_progress" }`
- "Dismiss" → Show small input for reason, then `PATCH /api/recommendations/{id}` with `{ status: "dismissed", status_note: reason }`
- Update UI optimistically using `queryClient.invalidateQueries`.

- [ ] **Step 5: Add expandable evidence panel**

On row expand, show `suggested_actions` from the JSONB field as a bulleted list. Show which banks/programs the recommendation relates to (if available in the data).

- [ ] **Step 6: Verify and commit**

```bash
git add dashboard/src/pages/Recommendations.tsx
git commit -m "feat: enhance Recommendations — status workflow, actions, pagination, evidence panel"
```

---

### Task 12: Bank Detail Page — Enhancement

**Files:**
- Modify: `dashboard/src/pages/BankDetail.tsx`

- [ ] **Step 1: Add CTA buttons to header**

Add "Crawl Now" and "Re-learn Strategy" buttons next to existing "Crawl This Bank". Use `apiPost('/api/crawl/crawler?bank=${bank_code}')` and `apiPost('/api/crawl/learning?bank=${bank_code}')`.

- [ ] **Step 2: Replace info section with 3 info cards**

Three cards across: Crawl Health (success rate, streak, last crawled, total), Strategy (bypass method, version, success bar, anti-bot badge), Data Quality (avg completeness, avg confidence, program count).

- [ ] **Step 3: Add CTAs on pipeline steps**

On failed Crawl step: show "Re-crawl" button.
On failed Parse step: show "Re-parse" button → `apiPost('/api/crawl/parser?bank=${bank_code}')`.

- [ ] **Step 4: Add Re-crawl CTA on failed crawl history rows**

For crawl log entries with failed/blocked status, add inline "Re-crawl" button.

- [ ] **Step 5: Verify and commit**

```bash
git add dashboard/src/pages/BankDetail.tsx
git commit -m "feat: enhance Bank Detail — health/quality cards, pipeline CTAs, re-crawl on history"
```

---

## Phase 4: Cleanup & Verification

### Task 13: Final Cleanup

- [ ] **Step 1: Remove unused StatsCard if fully replaced by KpiCard**

Check if any page still imports `StatsCard`. If not, delete it.

- [ ] **Step 2: Run TypeScript type check**

```bash
cd dashboard && npx tsc --noEmit
```

Fix any type errors.

- [ ] **Step 3: Run all backend tests**

```bash
python -m pytest tests/ -v --timeout=30
```

- [ ] **Step 4: Build frontend to verify no build errors**

```bash
cd dashboard && npm run build
```

- [ ] **Step 5: Manual smoke test all 7 pages**

Open each page in browser and verify:
- Overview: Health bar, KPI cards, Rate Intelligence table, alerts with CTAs, changes, quality
- Banks: Summary strip, bulk select, health/quality columns, sort
- Loan Programs: Summary strip, rate types, compare view, re-parse CTA
- Crawl Logs: Analytics strip, error breakdown, trend chart, re-crawl CTAs
- Strategies: Summary strip, sparklines, rebuild feedback
- Recommendations: Filter tabs, pagination, act/dismiss, evidence
- Bank Detail: Info cards, pipeline CTAs, history CTAs

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: cleanup — remove unused components, fix type errors"
```

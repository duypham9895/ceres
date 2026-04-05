# CERES Dashboard — Full Redesign Spec

**Date:** 2026-04-03
**Status:** Draft
**Scope:** All 7 dashboard pages

---

## Design Principles

1. **No Useless Data** — Every number, table, and alert must lead to a decision or action. If it can't, delete it.
2. **Every Alert Has a CTA** — Problems without solutions are noise. Every alert maps to an API action.
3. **Intelligence First** — Rate data and quality metrics get the most real estate. Health is glanceable.
4. **Actionable Over Informational** — Show "what to do" not just "what happened."

---

## Global Design Patterns

### Summary Strip
Every list page gets a thin summary strip at top showing aggregate counts with color-coded status. Replaces scattered stats.

### Actionable Tables
All tables support: sortable columns, multi-select with bulk actions, inline CTAs on problem rows.

### Data Quality Visibility
completeness_score and data_confidence are surfaced wherever loan program data appears — as bars, dots, or tooltips.

### Consistent Color Language
- Green (#4ade80): healthy, good rates (<6%), high quality
- Yellow (#fbbf24): warning, mid rates (6-8%), medium quality
- Red (#f87171): error, high rates (>8%), low quality
- Blue (#60a5fa): informational, pipeline, neutral metrics
- Purple (#a78bfa): interactive, tabs, actions

### Rate Color Coding
- **Absolute thresholds** on data tables (Rate Intelligence, Loan Programs list): <6% green, 6-8% yellow, >8% red
- **Relative ranking** on Compare View only: lowest rate gets green highlight, highest gets red highlight

### Responsive Behavior
- **Desktop (≥1280px):** Full layout as designed — 4 KPI cards, 65/35 split, side-by-side panels
- **Tablet (768–1279px):** KPI cards 2×2 grid, Rate Intelligence table goes full-width, right sidebar stacks below
- **Mobile (<768px):** Single column, KPI cards stack vertically, tables become card lists, health bar wraps

### Loading & Empty States
- **Loading:** Skeleton shimmer placeholders matching component shape (not "Loading..." text)
- **Empty — Needs Attention:** "All clear — no issues detected" with green checkmark
- **Empty — Today's Changes:** "No changes yet today. Last change: [relative time]"
- **Empty — Compare View:** "No [loan_type] programs found. Try a different loan type."
- **Empty — Recommendations:** "Run Learning" CTA button (keep existing pattern)

### Field Name Normalization
The frontend uses `min_tenure_months` / `max_tenure_months` but the database column is `min_tenor_months` / `max_tenor_months`. As part of this redesign, normalize to match the database: use `tenor` consistently.

---

## Page 1: Overview

### Layout: Dashboard Zones

**Zone 1 — Health Status Bar** (thin strip, top)
- Bank status counts with colored dots: `● 40 active · ● 13 unreachable · ● 5 blocked`
- Live pipeline progress: `Pipeline: Crawler ▶ 34/58 banks`
- 7-day success rate with trend: `64% success ↓8%`
- Data source: `/api/dashboard` (existing) + CrawlStatusContext (existing WebSocket)

**Zone 2 — KPI Cards** (4 across)
| Card | Value | Delta | Sparkline |
|------|-------|-------|-----------|
| Banks Monitored | total_banks | +N this week | 7-day bank count |
| Loan Programs | total_programs | +N new | 7-day program count |
| Avg KPR Rate | avg min_interest_rate | ↓/↑ vs last week | 7-day rate trend |
| Data Quality | avg completeness_score | avg completeness | 7-day quality trend |

- Data source: `/api/dashboard` (extend — see response contract below)

**Extended `/api/dashboard` Response Contract:**
```json
{
  "total_banks": 58,
  "total_programs": 288,
  "banks_by_status": {"active": 40, "unreachable": 13, "blocked": 5},
  "success_rate": 0.64,
  "crawl_stats": { ... },
  "quality_avg": 0.72,
  "deltas": {
    "banks_week": 3,
    "programs_new": 12,
    "kpr_rate_change": -0.3,
    "quality_change": 0.02
  },
  "sparklines": {
    "banks": [55, 55, 56, 56, 57, 57, 58],
    "programs": [270, 272, 275, 278, 280, 284, 288],
    "kpr_rate": [7.5, 7.4, 7.4, 7.3, 7.3, 7.2, 7.2],
    "quality": [0.68, 0.69, 0.70, 0.70, 0.71, 0.71, 0.72]
  }
}
```
Sparkline arrays = daily values for last 7 days. Computed from: banks.created_at counts, loan_programs.created_at counts, AVG(min_interest_rate) WHERE loan_type='KPR', AVG(completeness_score).

**Zone 3 — Rate Intelligence Table** (~65% width)
- Tabs: KPR | KPA | Multiguna | Kendaraan | All Types
- Columns: Bank (with status dot), Min Rate (color-coded), Max Rate, 7d Trend (chip), Completeness (bar), Confidence (dots)
- Sortable by any column
- Click row → Bank Detail page
- Data source: `/api/rates/heatmap` (extend with completeness, confidence, trend)

**Zone 4 — Right Sidebar** (~35% width, 3 stacked panels)

**Panel: Needs Attention** (with count badge)

All CTAs use the existing `POST /api/crawl/{agent_name}?bank={bank_code}` pattern:

| Alert Category | Trigger | CTA | API Call |
|---|---|---|---|
| Crawl Failure — unreachable | website_status = UNREACHABLE for 24h+ | Re-crawl All | `POST /api/crawl/crawler?bank={bank_code}` |
| Crawl Failure — anti-bot | last crawl blocked by anti-bot | Retry with Proxy | `POST /api/crawl/crawler?bank={bank_code}&force=true` |
| Rate Anomaly | rate changed >0.5% in 24h (compare current `is_latest=true` vs previous version of same program) | Verify Rate | `POST /api/crawl/crawler?bank={bank_code}` |
| Data Quality | completeness_score < 0.5 | Re-parse | `POST /api/crawl/parser?bank={bank_code}` |
| Stale Data | last_crawled_at > 3 days ago | Crawl Now | `POST /api/crawl/crawler?bank={bank_code}` |
| Strategy Health | success_rate < 0.3 | Re-learn | `POST /api/crawl/learning?bank={bank_code}` |

**Rate Anomaly Detection:** Compare `min_interest_rate` of the current `is_latest=true` loan_program row against the most recent `is_latest=false` row for the same `(bank_id, loan_type, program_name)`. Alert if absolute difference > 0.5%.

**Panel: Today's Changes**
- New programs discovered (count + "NEW" badge)
- Rate changes detected (count + "RATE" badge, split by increase/decrease)
- Bank status changes (count + "ALERT" badge)
- Data source: `GET /api/dashboard/changes` (NEW endpoint)

**Panel: Data Quality Summary**
- Three horizontal bars: High (>80%), Medium (50-80%), Low (<50%)
- Each bar shows bank count
- Data source: `GET /api/dashboard/quality` (NEW endpoint)

### Removed from Overview
- Live Activity feed (noise) → replaced by Today's Changes
- Old Rate Heatmap (broken) → replaced by tabbed Rate Intelligence
- Ring chart → inline in health bar
- Sidebar crawl progress panel → consolidated into health bar

---

## Page 2: Banks

### Layout: Summary Strip + Actionable Table

**Summary Strip**
- `X active · Y unreachable · Z blocked · W never crawled`
- Quick filter buttons: "Show Failing" | "Show Stale" | "All"

**Table Columns**
| Column | Source | Notes |
|--------|--------|-------|
| (checkbox) | — | Multi-select for bulk actions |
| Bank Name | bank_name | Primary identifier (not code) |
| Category | bank_category | Badge: BUMN, BPD, SWASTA, etc. |
| Status | website_status | Colored badge |
| Programs | count of is_latest programs | Number |
| Crawl Health | crawl_streak (from banks table) + rolling success rate (successful/total crawls in last 30d from crawl_logs) | Streak number + mini bar (e.g., "🔥5 · 80%") |
| Data Quality | avg completeness_score across programs | Progress bar |
| Last Crawled | last_crawled_at | Relative time ("2h ago", "3d ago" in red) |
| Actions | — | Crawl, Re-learn buttons |

**Bulk Actions Bar** (appears when rows selected)
- "Crawl Selected (N)" — triggers crawl for all selected banks
- "Re-learn Selected (N)" — triggers learning for selected banks
- "Clear Selection"

**Sorting:** All columns sortable. Default: Status (failing first), then Last Crawled (stale first).

**Data source:** `/api/banks` (extend response with crawl_health, avg_quality)

---

## Page 3: Loan Programs

### Layout: Mode Toggle + Enhanced Table

**Mode Toggle** (top right)
- **List View** (default): current table but enhanced
- **Compare View**: select loan type → see all banks side-by-side for that type

**Summary Strip**
- `X total programs · Y loan types · Z% avg completeness · W low-quality`

### List View — Table Columns
| Column | Source | Notes |
|--------|--------|-------|
| Program Name | program_name | With bank name subtitle |
| Loan Type | loan_type | Badge |
| Rate Range | min/max_interest_rate | "3.5% — 8.2%" color-coded |
| Rate Type | rate_fixed/floating/promo | Chips: "Fixed 5.5%" "Floating 8.2%" "Promo 3.5% (12mo)" |
| Completeness | completeness_score | Bar + percentage |
| Confidence | data_confidence | Dot rating (1-5) |
| Updated | updated_at | Relative time |
| Actions | — | Re-parse (if low quality) |

**Expandable Row Detail**
- Amount range & tenor range
- Source URL (clickable)
- Missing fields tooltip: "Missing: max_amount, min_tenor, employment_types"
- Rate history sparkline (if versioned data available)
- Raw data JSON viewer (collapsible)

### Compare View
- Select loan type from dropdown (KPR, KPA, etc.)
- Table: Bank | Min Rate | Max Rate | Fixed | Floating | Promo | Completeness
- Sorted by min rate (lowest first)
- Highlights: lowest rate (green highlight), highest rate (red highlight) — uses relative ranking, not absolute thresholds

**Data source:** `/api/loan-programs` (extend with rate type breakdown), `/api/loan-programs/compare?loan_type=KPR` (NEW)

---

## Page 4: Crawl Logs

### Layout: Analytics Strip + Enhanced Timeline

**Analytics Strip** (4 mini cards)
| Card | Value |
|------|-------|
| Total Crawls (7d) | count |
| Success Rate | percentage with trend |
| Avg Duration | milliseconds |
| Programs Found | total new + updated |

**Error Breakdown** (horizontal stacked bar below strip)
- Success (green) | Failed (red) | Blocked (yellow) | Timeout (gray)
- Percentages labeled, clickable to filter timeline below

**Success Rate Trend** (line chart, 30 days)
- Daily success rate plotted
- Red line at 70% threshold

**Enhanced Timeline**
- Grouped by date (existing pattern)
- Each entry shows: Bank name, Status badge, Duration, Programs found/new, Error type (if failed)
- Failed entries get inline "Re-crawl" CTA → `POST /api/crawl/crawler?bank={bank_code}`
- Blocked entries get inline "Retry" CTA → `POST /api/crawl/crawler?bank={bank_code}&force=true`

**Filters:** Status (multi-select), Bank, Date range, Error type

**Data source:** `/api/crawl-logs` (extend with aggregation), `/api/crawl-logs/analytics` (NEW — stats, error breakdown, trend)

---

## Page 5: Strategies

### Layout: Summary Strip + Enhanced Table (keep existing patterns, add missing features)

**Summary Strip**
- `X healthy · Y degraded · Z dead · W% avg success rate`
- Quick action: "Select all N failing strategies"

**Table Enhancements** (on top of existing)
| New Column | Source | Notes |
|------------|--------|-------|
| Success Trend | 30d success rate history | Sparkline |
| Version | version number | With "v3" badge |
| Last Tested | latest strategy_feedback | Relative time |

**Expandable Row Enhancements**
- Existing: bypass method, version, success bar, rebuild/test buttons
- NEW: Success rate history derived from `crawl_logs` (last 10 crawls grouped by strategy version, showing success rate per version period — not true version snapshots, since old strategy rows are overwritten by UPSERT)
- NEW: After rebuild, show per-bank status (queued/success/failed) instead of generic "queued" message

**Rebuild Feedback Improvement**
- Current: "Queued rebuild for N banks" (no feedback on which failed)
- New: Live progress indicator showing each bank's rebuild status
- Banks that failed to queue shown in red with error message

**Data source:** `/api/strategies` (extend with success_trend from crawl_logs), `/api/strategies/rebuild-all` (extend response feedback)

Note: Strategy version history is limited because `bank_strategies` uses UPSERT (overwrites in place). The "version history" is approximated by grouping crawl_logs by date ranges matching version increments. True version snapshots would require a schema change (deferred to v2).

---

## Page 6: Recommendations

### Layout: Priority List + Action System

**Summary Strip**
- `X total · Y action required · Z new this week · W dismissed`
- Filter tabs: All | Action Required | New | Reviewed | Dismissed

**Recommendation Cards → List Items**
Replace card grid with a priority-sorted list (more scannable):

| Field | Display |
|-------|---------|
| Priority | Stars (1-5) + color badge |
| Type | Colored chip (partnership/gap/competitive/pricing/trend) |
| Title | Bold text |
| Summary | 2-line description |
| Impact | Bar + explanation text ("Could improve crawl success by 15%") |
| Created | Relative time |
| Status | New → Reviewed → In Progress → Done / Dismissed |
| Actions | **Act** (mark in progress) · **Dismiss** (with reason) · **Snooze** (1 week) |

**Evidence Panel** (expandable)
- When expanding a recommendation, show supporting data:
  - Which banks/programs it relates to
  - Data points that triggered it
  - Suggested actions (from suggested_actions JSONB field)

**Status Workflow**
```
pending → reviewed → in_progress → done
                                 → dismissed
```
Note: Snooze feature deferred to v2. Keep scope simple — status is a VARCHAR(20) column that already exists. No schema migration needed for status values. Dismissed reason stored in a new `status_note` VARCHAR(500) column (schema migration required).

**Data source:** `/api/recommendations` (add pagination, filtering, status updates), `PATCH /api/recommendations/{id}` (NEW — update status)

**`PATCH /api/recommendations/{id}` Request/Response:**
```json
// Request
{ "status": "dismissed", "status_note": "Not relevant to current priorities" }

// Response
{ "id": "uuid", "status": "dismissed", "status_note": "...", "updated_at": "..." }
```

**`GET /api/recommendations` Query Params:**
- `?status=pending,reviewed` (comma-separated, filter by status)
- `?page=1&limit=20` (pagination)
- `?sort=priority` (sort by priority desc, then impact_score desc)

---

## Page 7: Bank Detail

### Layout: Header + 3-Column Info + Pipeline + Tables

**Bank Header**
- Bank name (large), bank code (subtitle), category badge, status badge
- CTA buttons: "Crawl Now" | "Re-learn Strategy" | "Visit Website" (external link)

**Info Cards** (3 across)
| Card | Content |
|------|---------|
| Crawl Health | Success rate (30d), crawl streak, last crawled relative time, total crawls |
| Strategy | Bypass method, version, success rate bar, anti-bot type badge |
| Data Quality | Avg completeness across programs, avg confidence, programs count |

**Pipeline Status** (enhanced)
- 3-step visualization: Crawl → Parse → Extract (keep existing)
- ADD: Duration per step
- ADD: "Re-crawl" / "Re-parse" CTAs on failed steps
- ADD: Last run timestamp per step

**Loan Programs Table**
- Same columns as Loan Programs page but filtered to this bank
- Expandable rows with full detail
- "Re-parse" CTA on low-quality programs

**Crawl History Table**
- Last 20 crawl logs for this bank
- Columns: Date, Status, Duration, Pages, Programs Found/New, Error
- Failed rows get "Re-crawl" CTA
- Sortable by date

**Data source:** `/api/banks/{id}` (extend with crawl_health, quality metrics)

---

## New Backend Endpoints Required

### New GET Endpoints

**`GET /api/dashboard/alerts`** — Aggregated alerts across 5 categories
```json
{
  "total": 11,
  "alerts": [
    {
      "category": "crawl_failure",
      "type": "unreachable",
      "message": "5 banks unreachable for 24h+",
      "count": 5,
      "bank_codes": ["bengkulu", "kalbar", ...],
      "cta": { "label": "Re-crawl All", "agent": "crawler" }
    },
    {
      "category": "rate_anomaly",
      "type": "spike",
      "message": "BRI KPR rate spiked +0.5% in 24h",
      "count": 1,
      "bank_codes": ["bri"],
      "cta": { "label": "Verify Rate", "agent": "crawler" }
    }
  ]
}
```

**`GET /api/dashboard/changes`** — Today's meaningful changes
```json
{
  "date": "2026-04-03",
  "changes": [
    { "type": "new_programs", "count": 12, "detail": "12 new loan programs discovered" },
    { "type": "rate_decrease", "count": 3, "detail": "3 banks decreased KPR rates" },
    { "type": "rate_increase", "count": 1, "detail": "1 bank increased KPR rate" },
    { "type": "status_change", "count": 2, "detail": "2 banks came back online" }
  ]
}
```

**`GET /api/dashboard/quality`** — Data quality distribution
```json
{
  "high": { "count": 32, "threshold": 0.8 },
  "medium": { "count": 18, "threshold": 0.5 },
  "low": { "count": 8, "threshold": 0.0 },
  "avg_completeness": 0.72
}
```

**`GET /api/crawl-logs/analytics`** — Crawl stats, error breakdown, success trend
```json
{
  "stats": {
    "total_crawls_7d": 412,
    "success_rate": 0.64,
    "success_rate_prev_week": 0.72,
    "avg_duration_ms": 45000,
    "programs_found": 288,
    "programs_new": 12
  },
  "error_breakdown": {
    "success": 264, "failed": 78, "blocked": 42, "timeout": 28
  },
  "daily_success_rate": [
    { "date": "2026-03-04", "rate": 0.70 },
    { "date": "2026-03-05", "rate": 0.68 }
  ]
}
```

**`GET /api/loan-programs/compare?loan_type=KPR`** — Side-by-side comparison
```json
{
  "loan_type": "KPR",
  "programs": [
    {
      "bank_code": "bca_syariah",
      "bank_name": "BCA Syariah",
      "min_interest_rate": 3.5,
      "max_interest_rate": 8.25,
      "rate_fixed": 5.5,
      "rate_floating": 8.25,
      "rate_promo": 3.5,
      "rate_promo_duration_months": 12,
      "completeness_score": 0.9
    }
  ]
}
```

### New PATCH Endpoint

**`PATCH /api/recommendations/{id}`** — Update recommendation status (see Page 6 section for request/response contract)

### CTA Actions — All Use Existing Pattern

All CTAs trigger `POST /api/crawl/{agent_name}?bank={bank_code}` which already exists. No new POST endpoints needed for CTAs. The `agent_name` parameter selects the agent: `crawler`, `parser`, `learning`.

### Extended Existing Endpoints
| Endpoint | Extension |
|----------|-----------|
| `GET /api/dashboard` | Add quality_avg, deltas, sparklines (see response contract in Page 1) |
| `GET /api/rates/heatmap` | Add completeness_score, data_confidence, 7d trend per bank |
| `GET /api/banks` | Add crawl_health (streak + 30d success rate), avg_quality per bank |
| `GET /api/banks/{id}` | Add crawl_health, quality metrics |
| `GET /api/strategies` | Add success_trend (last 30d daily success from crawl_logs) |
| `GET /api/recommendations` | Add pagination (?page, ?limit), status filtering (?status=), sorting (?sort=) |
| `GET /api/loan-programs` | Add rate_fixed, rate_floating, rate_promo, rate_promo_duration_months to response |

### Schema Migration Required

```sql
-- Add status_note to recommendations for dismiss reasons
ALTER TABLE ringkas_recommendations ADD COLUMN status_note VARCHAR(500);
```

No other schema changes needed for v1. Strategy version history is derived from crawl_logs, not stored separately.

---

## Frontend Components to Create

| Component | Used By |
|-----------|---------|
| `SummaryStrip` | All list pages |
| `ActionableTable` | Banks, Strategies, Crawl Logs |
| `SparklineBar` | KPI cards, Strategy trend |
| `CompletenessBar` | Rate Intelligence, Loan Programs, Bank Detail |
| `ConfidenceDots` | Rate Intelligence, Loan Programs |
| `TrendChip` | Rate Intelligence, Crawl Logs |
| `AlertItem` | Overview Needs Attention panel |
| `ChangeItem` | Overview Today's Changes panel |
| `QualitySummary` | Overview, Bank Detail |
| `CompareTable` | Loan Programs compare mode |
| `CrawlAnalytics` | Crawl Logs analytics strip + charts |
| `VersionTimeline` | Strategies expanded row |
| `RecommendationItem` | Recommendations list |
| `EvidencePanel` | Recommendations expanded |

## Frontend Components to Remove

| Component | Reason |
|-----------|--------|
| `LiveFeed` | Replaced by Today's Changes |
| `RingChart` | Success rate moved to health bar inline |
| `RateHeatmap` | Replaced by tabbed Rate Intelligence table |

**Note:** `Overview.tsx` imports all three removed components — it requires a full rewrite, not incremental modification. All other pages can be incrementally enhanced.

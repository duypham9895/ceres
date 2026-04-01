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

import { useQuery } from '@tanstack/react-query';
import { apiFetch, apiPost } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import type { CrawlAnalytics } from '../types/dashboard';
import TimelineEvent, { type CrawlLog } from '../components/TimelineEvent';
import { useFilterState } from '../hooks/useFilterState';
import { CRAWL_LOG_FILTERS } from '../config/filters';
import FilterBar from '../components/filters/FilterBar';
import { SkeletonCard } from '../components/Skeleton';
import { toast } from 'sonner';
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

const LIMIT = 20;

const STATUS_COLORS: Record<string, string> = {
  success: 'bg-success',
  failed: 'bg-error',
  blocked: 'bg-warning',
  timeout: 'bg-text-dim',
};

function groupByDate(logs: readonly CrawlLog[]): Map<string, CrawlLog[]> {
  const groups = new Map<string, CrawlLog[]>();
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  for (const log of logs) {
    const dateStr = new Date(log.started_at).toDateString();
    const label = dateStr === today ? 'Today'
      : dateStr === yesterday ? 'Yesterday'
      : new Date(log.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    const existing = groups.get(label);
    if (existing) {
      groups.set(label, [...existing, log]);
    } else {
      groups.set(label, [log]);
    }
  }
  return groups;
}

function AnalyticsStrip({ analytics, isLoading }: { analytics: CrawlAnalytics | undefined; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }
  if (!analytics) return null;

  const { stats, error_breakdown, daily_success_rate } = analytics;
  const successRatePct = Math.round(stats.success_rate * 100);
  const prevWeekPct = Math.round(stats.success_rate_prev_week * 100);
  const delta = successRatePct - prevWeekPct;
  const total = Object.values(error_breakdown).reduce((a, b) => a + b, 0);

  return (
    <>
      {/* 4 mini KPI cards */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="bg-bg-card border border-border-light rounded-xl p-3">
          <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Total Crawls (7d)</p>
          <p className="text-xl font-semibold text-text-heading">{stats.total_crawls_7d}</p>
        </div>
        <div className="bg-bg-card border border-border-light rounded-xl p-3">
          <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Success Rate</p>
          <p className="text-xl font-semibold text-text-heading">{successRatePct}%</p>
          <p className={`text-[10px] ${delta >= 0 ? 'text-success' : 'text-error'}`}>
            {delta >= 0 ? '+' : ''}{delta}% vs prev week
          </p>
        </div>
        <div className="bg-bg-card border border-border-light rounded-xl p-3">
          <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Avg Duration</p>
          <p className="text-xl font-semibold text-text-heading">{(stats.avg_duration_ms / 1000).toFixed(1)}s</p>
        </div>
        <div className="bg-bg-card border border-border-light rounded-xl p-3">
          <p className="text-[10px] text-text-muted uppercase tracking-wide mb-1">Programs Found</p>
          <p className="text-xl font-semibold text-text-heading">{stats.programs_found}</p>
          <p className="text-[10px] text-success">+{stats.programs_new} new</p>
        </div>
      </div>

      {/* Error breakdown bar */}
      <div className="bg-bg-card border border-border-light rounded-xl p-4 mb-4">
        <p className="text-xs text-text-muted mb-2">Status Breakdown</p>
        <div className="flex h-3 rounded-full overflow-hidden bg-bg-hover mb-2">
          {Object.entries(error_breakdown).map(([status, count]) => (
            <div
              key={status}
              style={{ width: `${(count / total) * 100}%` }}
              className={STATUS_COLORS[status] ?? 'bg-text-dim'}
              title={`${status}: ${count}`}
            />
          ))}
        </div>
        <p className="text-[10px] text-text-muted">
          {Object.entries(error_breakdown).map(([status, count], i) => (
            <span key={status}>
              {i > 0 && ' · '}
              <span className="capitalize">{status}</span> {count} ({Math.round((count / total) * 100)}%)
            </span>
          ))}
        </p>
      </div>

      {/* Trend chart */}
      <div className="bg-bg-card rounded-xl border border-border-light p-4 mb-4">
        <p className="text-xs text-text-muted mb-2">Success Rate Trend (30d)</p>
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={daily_success_rate as Array<{ date: string; rate: number }>}>
            <XAxis dataKey="date" tick={{ fontSize: 9 }} stroke="#666" />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 9 }}
              stroke="#666"
            />
            <Tooltip formatter={(v) => `${Math.round(Number(v) * 100)}%`} />
            <ReferenceLine
              y={0.7}
              stroke="#f87171"
              strokeDasharray="3 3"
              label={{ value: '70%', fontSize: 9, fill: '#f87171' }}
            />
            <Line type="monotone" dataKey="rate" stroke="#a78bfa" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

export default function CrawlLogs() {
  const {
    filters, setFilter, setFilters, clearAll, clearFilter,
    toQueryString, activeCount, page, setPage,
  } = useFilterState(CRAWL_LOG_FILTERS);

  const queryString = toQueryString();
  const paginatedQuery = queryString
    ? `${queryString}&page=${page}&limit=${LIMIT}`
    : `page=${page}&limit=${LIMIT}`;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['crawl-logs', queryString, page],
    queryFn: () =>
      apiFetch<PaginatedResponse<CrawlLog>>(`/api/crawl-logs?${paginatedQuery}`),
  });

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['crawl-analytics'],
    queryFn: () => apiFetch<CrawlAnalytics>('/api/crawl-logs/analytics'),
    staleTime: 30_000,
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;
  const grouped = data ? groupByDate(data.data) : new Map();

  return (
    <div>
      <h2 className="text-xl font-semibold text-text-heading mb-6">Crawl Logs</h2>

      <AnalyticsStrip analytics={analytics} isLoading={analyticsLoading} />

      <FilterBar
        config={CRAWL_LOG_FILTERS}
        filters={filters}
        onFilterChange={setFilter}
        onFilterChangeBatch={setFilters}
        onClearAll={clearAll}
        onClearFilter={clearFilter}
        activeCount={activeCount}
        pageKey="crawl-logs"
        totalResults={data?.total}
      />

      {isLoading && <p className="text-text-muted">Loading crawl logs...</p>}
      {isError && <p className="text-error">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
            {data.data.length === 0 ? (
              <p className="px-4 py-8 text-center text-text-muted">No crawl logs found.</p>
            ) : (
              Array.from(grouped.entries()).map(([dateLabel, logs]: [string, CrawlLog[]]) => (
                <div key={dateLabel}>
                  <div className="px-4 py-2 bg-bg-primary/50 border-b border-border">
                    <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wide">
                      {dateLabel}
                    </span>
                  </div>
                  {logs.map((log) => (
                    <div key={log.id} className="flex items-center">
                      <div className="flex-1 min-w-0">
                        <TimelineEvent log={log} />
                      </div>
                      {(log.status === 'failed' || log.status === 'blocked') && log.bank_code && (
                        <button
                          onClick={() =>
                            apiPost(
                              `/api/crawl/crawler?bank=${log.bank_code}${log.status === 'blocked' ? '&force=true' : ''}`,
                              {}
                            ).then(() => toast.success('Re-crawl triggered'))
                          }
                          className="text-[10px] font-medium text-accent hover:text-accent/80 ml-2 pr-4 shrink-0"
                        >
                          {log.status === 'blocked' ? 'Retry' : 'Re-crawl'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-[12px] text-text-muted">
              {data.total === 0
                ? 'No results'
                : `Showing ${(page - 1) * LIMIT + 1}-${Math.min(page * LIMIT, data.total)} of ${data.total}`}
            </p>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 text-[12px] border border-border rounded-md text-text-secondary disabled:opacity-50 hover:bg-bg-hover"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span className="px-3 py-1 text-[12px] text-text-muted">
                Page {page} of {totalPages}
              </span>
              <button
                className="px-3 py-1 text-[12px] border border-border rounded-md text-text-secondary disabled:opacity-50 hover:bg-bg-hover"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

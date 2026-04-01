import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import TimelineEvent, { type CrawlLog } from '../components/TimelineEvent';

const STATUS_OPTIONS = ['success', 'failed', 'blocked', 'timeout', 'partial'] as const;
const LIMIT = 20;

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

export default function CrawlLogs() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');

  const queryParams = new URLSearchParams({
    page: String(page),
    limit: String(LIMIT),
  });
  if (statusFilter) queryParams.set('status', statusFilter);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['crawl-logs', page, statusFilter],
    queryFn: () =>
      apiFetch<PaginatedResponse<CrawlLog>>(`/api/crawl-logs?${queryParams.toString()}`),
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;
  const grouped = data ? groupByDate(data.data) : new Map();

  return (
    <div>
      <h2 className="text-xl font-semibold text-text-heading mb-6">Crawl Logs</h2>

      {/* Filter */}
      <div className="flex gap-4 mb-6">
        <select
          className="bg-bg-card border border-border rounded-md px-3 py-2 text-[13px] text-text-body"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

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
                    <TimelineEvent key={log.id} log={log} />
                  ))}
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-[12px] text-text-muted">
              Showing {(page - 1) * LIMIT + 1}-{Math.min(page * LIMIT, data.total)} of {data.total}
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

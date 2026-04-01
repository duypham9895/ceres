import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import StatusBadge from '../components/StatusBadge';

const STATUS_OPTIONS = ['success', 'failed', 'blocked', 'timeout', 'partial'] as const;

interface CrawlLog {
  readonly id: string;
  readonly started_at: string;
  readonly bank_code: string;
  readonly status: string;
  readonly duration_ms: number | null;
  readonly programs_found: number;
  readonly error_message: string | null;
}

const LIMIT = 20;

const ROW_COLORS: Record<string, string> = {
  success: 'bg-green-50',
  failed: 'bg-red-50',
  blocked: 'bg-yellow-50',
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay > 7) return date.toLocaleDateString();
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHour > 0) return `${diffHour}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return 'just now';
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  return `${(ms / 1000).toFixed(1)}s`;
}

function truncate(text: string | null, max: number): string {
  if (!text) return '-';
  return text.length > max ? `${text.slice(0, max)}...` : text;
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

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Crawl Logs</h2>

      {/* Filter */}
      <div className="flex gap-4 mb-6">
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-gray-500">Loading crawl logs...</p>}
      {isError && <p className="text-red-600">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bank</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Programs Found</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.data.map((log) => (
                  <tr key={log.id} className={ROW_COLORS[log.status] ?? ''}>
                    <td className="px-4 py-3 text-sm text-gray-600" title={log.started_at}>
                      {formatRelativeTime(log.started_at)}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{log.bank_code}</td>
                    <td className="px-4 py-3 text-sm">
                      <StatusBadge status={log.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{formatDuration(log.duration_ms)}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{log.programs_found}</td>
                    <td className="px-4 py-3 text-sm text-gray-500" title={log.error_message ?? ''}>
                      {truncate(log.error_message, 50)}
                    </td>
                  </tr>
                ))}
                {data.data.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      No crawl logs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-600">
              Showing {(page - 1) * LIMIT + 1}-{Math.min(page * LIMIT, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 text-sm border rounded disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <button
                className="px-3 py-1 text-sm border rounded disabled:opacity-50"
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

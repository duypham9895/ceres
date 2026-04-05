import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import { formatShortDate, formatShortDateTime } from '../utils/format';
import SummaryStrip from '../components/SummaryStrip';
import CrawlButton from '../components/CrawlButton';

interface AgentRun {
  readonly agent_name: string;
  readonly status: string;
  readonly started_at: string;
  readonly finished_at: string | null;
  readonly error_message: string | null;
}

interface Recommendation {
  readonly id: string;
  readonly rec_type: string;
  readonly title: string;
  readonly summary: string;
  readonly priority: number;
  readonly impact_score: number;
  readonly created_at: string;
  readonly status: string;
  readonly status_note?: string;
  readonly suggested_actions?: string[];
}

const LIMIT = 20;

const TABS = [
  { label: 'All', value: '' },
  { label: 'Action Required', value: 'pending' },
  { label: 'Reviewed', value: 'reviewed' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Done', value: 'done' },
  { label: 'Dismissed', value: 'dismissed' },
];

const REC_TYPE_COLORS: Record<string, string> = {
  partnership_opportunity: 'bg-running/15 text-running-dim',
  product_gap: 'bg-warning/15 text-warning-dim',
  competitive_analysis: 'bg-success/15 text-success-dim',
  pricing: 'bg-accent/15 text-accent-light',
  market_trend: 'bg-success/15 text-success-dim',
};

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-warning/10 text-warning',
  reviewed: 'bg-running/10 text-running',
  in_progress: 'bg-accent/10 text-accent',
  done: 'bg-success/10 text-success',
  dismissed: 'bg-text-dim/10 text-text-dim',
};

function formatRecType(recType: string): string {
  return recType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function PriorityStars({ priority }: { readonly priority: number }) {
  const clamped = Math.max(1, Math.min(5, priority));
  return (
    <div className="flex gap-0.5" title={`Priority: ${clamped}/5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} className={i < clamped ? 'text-warning' : 'text-text-dim'}>
          ★
        </span>
      ))}
    </div>
  );
}

function ImpactBar({ score }: { readonly score: number }) {
  const percentage = Math.round(score * 100);
  const barColor = percentage >= 70 ? 'bg-success' : percentage >= 40 ? 'bg-warning' : 'bg-error';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-border rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm font-[var(--font-mono)] text-text-secondary w-10 text-right">{percentage}%</span>
    </div>
  );
}

function RecTypeBadge({ recType }: { readonly recType: string }) {
  const colorClass = REC_TYPE_COLORS[recType] ?? 'bg-border text-text-secondary';
  return (
    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
      {formatRecType(recType)}
    </span>
  );
}

function StatusBadge({ status }: { readonly status: string }) {
  const colorClass = STATUS_STYLES[status] ?? 'bg-border text-text-secondary';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {formatRecType(status)}
    </span>
  );
}

interface RecItemProps {
  readonly rec: Recommendation;
  readonly onStatusChange: (id: string, status: string, statusNote?: string) => void;
  readonly isPending: boolean;
}

function RecItem({ rec, onStatusChange, isPending }: RecItemProps) {
  const [expanded, setExpanded] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [dismissNote, setDismissNote] = useState('');

  const handleDismissSubmit = () => {
    onStatusChange(rec.id, 'dismissed', dismissNote || undefined);
    setDismissing(false);
    setDismissNote('');
  };

  return (
    <div className="bg-bg-card rounded-lg border border-border overflow-hidden">
      <button
        className="w-full text-left p-4 hover:bg-bg-hover transition-colors"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <div className="flex items-start gap-3">
          <div className="flex flex-col items-start gap-1 min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <PriorityStars priority={rec.priority} />
              <RecTypeBadge recType={rec.rec_type} />
              <StatusBadge status={rec.status} />
            </div>
            <p className="font-semibold text-text-heading text-sm">{rec.title}</p>
            <p className="text-xs text-text-secondary line-clamp-2">{rec.summary}</p>
            <div className="w-full mt-1">
              <p className="text-xs text-text-muted mb-1">Impact</p>
              <ImpactBar score={rec.impact_score} />
            </div>
          </div>
          <div className="text-xs text-text-dim whitespace-nowrap mt-1">{formatShortDate(rec.created_at)}</div>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-border px-4 py-3 bg-bg-surface space-y-3">
          <div>
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-2">Suggested Actions</p>
            {rec.suggested_actions && rec.suggested_actions.length > 0 ? (
              <ul className="list-disc list-inside space-y-1">
                {rec.suggested_actions.map((action, i) => (
                  <li key={i} className="text-xs text-text-secondary">
                    {action}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-text-dim">No suggested actions for this recommendation.</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {rec.status === 'pending' && (
              <button
                disabled={isPending}
                onClick={() => onStatusChange(rec.id, 'reviewed')}
                className="px-3 py-1 text-xs rounded bg-running/10 text-running border border-running/30 hover:bg-running/20 disabled:opacity-50"
              >
                Mark as Reviewed
              </button>
            )}
            {(rec.status === 'pending' || rec.status === 'reviewed') && (
              <button
                disabled={isPending}
                onClick={() => onStatusChange(rec.id, 'in_progress')}
                className="px-3 py-1 text-xs rounded bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 disabled:opacity-50"
              >
                Act
              </button>
            )}
            {rec.status === 'in_progress' && (
              <button
                disabled={isPending}
                onClick={() => onStatusChange(rec.id, 'done')}
                className="px-3 py-1 text-xs rounded bg-success/10 text-success border border-success/30 hover:bg-success/20 disabled:opacity-50"
              >
                Done
              </button>
            )}
            {rec.status !== 'dismissed' && rec.status !== 'done' && !dismissing && (
              <button
                disabled={isPending}
                onClick={() => setDismissing(true)}
                className="px-3 py-1 text-xs rounded bg-text-dim/10 text-text-dim border border-text-dim/30 hover:bg-text-dim/20 disabled:opacity-50"
              >
                Dismiss
              </button>
            )}
            {dismissing && (
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  type="text"
                  value={dismissNote}
                  onChange={(e) => setDismissNote(e.target.value)}
                  placeholder="Reason (optional)"
                  className="text-xs px-2 py-1 rounded border border-border bg-bg-input text-text-body focus:outline-none focus:border-accent"
                />
                <button
                  disabled={isPending}
                  onClick={handleDismissSubmit}
                  className="px-3 py-1 text-xs rounded bg-text-dim/10 text-text-dim border border-text-dim/30 hover:bg-text-dim/20 disabled:opacity-50"
                >
                  Confirm
                </button>
                <button
                  onClick={() => { setDismissing(false); setDismissNote(''); }}
                  className="px-3 py-1 text-xs rounded border border-border text-text-muted hover:bg-bg-hover"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Recommendations() {
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const params = new URLSearchParams({ page: String(page), limit: String(LIMIT), sort: 'priority' });
  if (statusFilter) params.set('status', statusFilter);

  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations', statusFilter, page],
    queryFn: () => apiFetch<PaginatedResponse<Recommendation>>(`/api/recommendations?${params}`),
  });

  const { data: agentRuns } = useQuery({
    queryKey: ['agent-runs-latest'],
    queryFn: () => apiFetch<{ data: AgentRun[] }>('/api/agent-runs/latest').then((r) => r.data),
    enabled: !data || data.total === 0,
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status, status_note }: { id: string; status: string; status_note?: string }) =>
      apiFetch(`/api/recommendations/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, status_note }),
        headers: { 'Content-Type': 'application/json' },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      toast.success('Status updated');
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : 'Failed to update status');
    },
  });

  const handleStatusChange = (id: string, status: string, statusNote?: string) => {
    updateStatus.mutate({ id, status, status_note: statusNote });
  };

  if (isLoading) return <p className="text-text-muted">Loading recommendations...</p>;

  if (error) {
    return (
      <div className="text-error">
        <p>Failed to load recommendations: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.total === 0) {
    const lastRun = agentRuns?.find((r) => r.agent_name === 'learning');
    return (
      <div>
        <h2 className="text-2xl font-bold text-text-heading mb-6">Recommendations</h2>
        <div className="bg-bg-card rounded-lg border border-border p-6">
          <p className="text-text-muted mb-3">No recommendations yet.</p>
          {lastRun ? (
            <div className="text-sm space-y-1 mb-4">
              <p className="text-text-secondary">
                Last learning run:{' '}
                <span
                  className={
                    lastRun.status === 'success'
                      ? 'text-success'
                      : lastRun.status === 'failed'
                        ? 'text-error'
                        : 'text-warning'
                  }
                >
                  {lastRun.status.toUpperCase()}
                </span>{' '}
                at {formatShortDateTime(lastRun.started_at)}
              </p>
              {lastRun.error_message && (
                <p className="text-error text-xs font-[var(--font-mono)]">Error: {lastRun.error_message}</p>
              )}
            </div>
          ) : (
            <p className="text-text-dim text-sm mb-4">Learning agent has never been run.</p>
          )}
          <CrawlButton agent="learning" label="Run Learning" />
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / LIMIT);

  const summaryItems = (() => {
    const items = data?.data ?? [];
    const pendingCount = items.filter((r) => r.status === 'pending').length;
    const inProgressCount = items.filter((r) => r.status === 'in_progress').length;
    const doneCount = items.filter((r) => r.status === 'done').length;
    const dismissedCount = items.filter((r) => r.status === 'dismissed').length;
    return [
      { label: 'pending', value: pendingCount, color: 'yellow' as const },
      { label: 'in progress', value: inProgressCount, color: 'blue' as const },
      { label: 'done', value: doneCount, color: 'green' as const },
      { label: 'dismissed', value: dismissedCount, color: 'gray' as const },
    ];
  })();

  return (
    <div>
      <h2 className="text-2xl font-bold text-text-heading mb-4">Recommendations</h2>

      <SummaryStrip items={summaryItems} />

      <div className="flex gap-1 mb-4">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => { setStatusFilter(tab.value); setPage(1); }}
            className={`px-3 py-1 rounded text-xs font-medium ${
              statusFilter === tab.value ? 'bg-accent/10 text-accent' : 'text-text-dim hover:text-text-muted'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        {data.data.map((rec) => (
          <RecItem
            key={rec.id}
            rec={rec}
            onStatusChange={handleStatusChange}
            isPending={updateStatus.isPending}
          />
        ))}
      </div>

      <div className="flex items-center justify-between mt-4">
        <span className="text-xs text-text-dim">{data.total} recommendations</span>
        <div className="flex gap-2 items-center">
          <button
            className="px-3 py-1 text-sm border border-border rounded disabled:opacity-50 hover:bg-bg-hover text-text-body"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span className="text-xs text-text-dim">
            Page {page} of {totalPages}
          </span>
          <button
            className="px-3 py-1 text-sm border border-border rounded disabled:opacity-50 hover:bg-bg-hover text-text-body"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

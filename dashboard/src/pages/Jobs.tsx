import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, apiPost } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import SummaryStrip from '../components/SummaryStrip';
import { formatShortDateTime } from '../utils/format';

interface QueueStatus {
  readonly pending: number;
  readonly running: number;
  readonly failed: number;
  readonly recent_completions: number;
}

interface AgentRun {
  readonly agent_name: string;
  readonly status: string;
  readonly started_at: string;
  readonly finished_at: string | null;
  readonly error_message: string | null;
}

function computeDuration(started: string, finished: string | null): string {
  const start = new Date(started).getTime();
  const end = finished ? new Date(finished).getTime() : Date.now();
  const diffMs = end - start;
  if (diffMs < 1000) return '<1s';
  if (diffMs < 60_000) return `${(diffMs / 1000).toFixed(1)}s`;
  return `${(diffMs / 60_000).toFixed(1)}m`;
}

const REFRESH_INTERVAL = 10_000;

const STATUS_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Running', value: 'running' },
  { label: 'Failed', value: 'failed' },
  { label: 'Completed', value: 'success' },
] as const;

export default function Jobs() {
  const queryClient = useQueryClient();
  const [isCancelling, setIsCancelling] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [retryingAgent, setRetryingAgent] = useState<string | null>(null);

  const { data: queueStatus, isLoading: queueLoading } = useQuery({
    queryKey: ['queue-status'],
    queryFn: () => apiFetch<QueueStatus>('/api/queue/status'),
    refetchInterval: REFRESH_INTERVAL,
  });

  const { data: agentRunsResp, isLoading: runsLoading } = useQuery({
    queryKey: ['agent-runs-latest'],
    queryFn: () => apiFetch<{ data: AgentRun[] }>('/api/agent-runs/latest'),
    refetchInterval: REFRESH_INTERVAL,
  });

  const allAgentRuns = agentRunsResp?.data ?? [];
  const agentRuns = statusFilter
    ? allAgentRuns.filter((r) => r.status === statusFilter)
    : allAgentRuns;

  const handleCancelAll = async () => {
    setIsCancelling(true);
    try {
      await apiPost('/api/jobs/cancel');
      toast.success('All jobs cancelled');
      queryClient.invalidateQueries({ queryKey: ['queue-status'] });
      queryClient.invalidateQueries({ queryKey: ['agent-runs-latest'] });
    } catch {
      toast.error('Failed to cancel jobs');
    }
    setIsCancelling(false);
    setConfirmCancel(false);
  };

  const handleRetry = async (agentName: string) => {
    setRetryingAgent(agentName);
    try {
      await apiPost(`/api/crawl/${agentName}`);
      toast.success(`Retry triggered for ${agentName}`);
      queryClient.invalidateQueries({ queryKey: ['agent-runs-latest'] });
    } catch {
      toast.error(`Failed to retry ${agentName}`);
    }
    setRetryingAgent(null);
  };

  const isLoading = queueLoading || runsLoading;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-text-heading">Jobs</h2>
        <div className="flex items-center gap-2">
          {confirmCancel ? (
            <>
              <span className="text-xs text-text-muted">Cancel all running and pending jobs?</span>
              <button
                onClick={handleCancelAll}
                disabled={isCancelling}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-error text-white hover:bg-error/80 disabled:opacity-50"
              >
                {isCancelling ? 'Cancelling...' : 'Yes, Cancel All'}
              </button>
              <button
                onClick={() => setConfirmCancel(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:text-text-body border border-border"
              >
                No
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmCancel(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-error/10 text-error border border-error/20 hover:bg-error/20"
            >
              Cancel All
            </button>
          )}
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-1 mb-3">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              statusFilter === f.value ? 'bg-accent/10 text-accent' : 'text-text-dim hover:text-text-muted'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-text-muted">Loading job status...</p>}

      {queueStatus && (
        <SummaryStrip items={[
          { label: 'pending', value: queueStatus.pending, color: 'yellow' },
          { label: 'running', value: queueStatus.running, color: 'blue' },
          { label: 'completed (1h)', value: queueStatus.recent_completions, color: 'green' },
          { label: 'failed', value: queueStatus.failed, color: 'red' },
        ]} />
      )}

      <div className="bg-bg-card rounded-lg border border-border">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-heading">Recent Agent Runs</h3>
          <span className="text-[10px] text-text-dim">Auto-refreshes every 10s</span>
        </div>

        {agentRuns.length === 0 ? (
          <p className="px-6 py-8 text-center text-sm text-text-muted">No recent agent runs found.</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Started</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Error</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {agentRuns.map((run, idx) => (
                <tr key={`${run.agent_name}-${run.started_at}-${idx}`} className="hover:bg-bg-hover">
                  <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-heading">
                    {run.agent_name}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-text-secondary">
                    {formatShortDateTime(run.started_at)}
                  </td>
                  <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">
                    {computeDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-error max-w-xs truncate">
                    {run.error_message || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {run.status === 'failed' && (
                      <button
                        onClick={() => handleRetry(run.agent_name)}
                        disabled={retryingAgent === run.agent_name}
                        className="text-[10px] font-medium text-accent hover:text-accent/80 border border-accent/20 rounded px-2 py-0.5 disabled:opacity-50"
                      >
                        {retryingAgent === run.agent_name ? 'Retrying...' : 'Retry'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

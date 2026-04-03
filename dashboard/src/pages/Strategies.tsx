import { Fragment, useState, useRef, useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, apiPost } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import { formatShortDateTime } from '../utils/format';
import CrawlButton from '../components/CrawlButton';
import SummaryStrip from '../components/SummaryStrip';
import SparklineBar from '../components/SparklineBar';
import { useFilterState } from '../hooks/useFilterState';
import { STRATEGY_FILTERS } from '../config/filters';
import FilterBar from '../components/filters/FilterBar';

interface Strategy {
  readonly bank_code: string;
  readonly bank_name: string;
  readonly bypass_method: string;
  readonly anti_bot_type: string | null;
  readonly success_rate: number;
  readonly version: number;
  readonly updated_at: string;
  readonly success_trend?: number[];
}

interface AgentRun {
  readonly agent_name: string;
  readonly status: string;
  readonly started_at: string;
  readonly finished_at: string | null;
  readonly error_message: string | null;
}

type PillStatus = 'DEAD' | 'DEGRADED' | 'HEALTHY' | 'STRONG';

function getStatus(rate: number): PillStatus {
  if (rate === 0) return 'DEAD';
  if (rate < 0.5) return 'DEGRADED';
  if (rate >= 0.8) return 'STRONG';
  return 'HEALTHY';
}

const PILL_STYLES: Record<PillStatus, string> = {
  DEAD: 'bg-error/20 text-error',
  DEGRADED: 'bg-warning/20 text-warning',
  HEALTHY: 'bg-success/20 text-success',
  STRONG: 'bg-success/30 text-success font-bold',
};

function StatusPill({ rate }: { readonly rate: number }) {
  const status = getStatus(rate);
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${PILL_STYLES[status]}`}>
      {status}
    </span>
  );
}

function SuccessRateBar({ rate }: { readonly rate: number }) {
  const percentage = Math.round(rate * 100);
  const barColor = percentage >= 80 ? 'bg-success' : percentage >= 50 ? 'bg-warning' : 'bg-error';

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-border rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm font-[var(--font-mono)] text-text-secondary">{percentage}%</span>
    </div>
  );
}

function AntiBotBadge({ type }: { readonly type: string | null }) {
  if (!type || type === 'None') {
    return <span className="text-text-dim text-[11px]">None</span>;
  }
  return (
    <span className="px-2 py-0.5 rounded-full text-[11px] bg-warning/10 text-warning">
      {type}
    </span>
  );
}

const LIMIT = 20;

export default function Strategies() {
  const {
    filters, setFilter, setFilters, clearAll, clearFilter,
    toQueryString, activeCount, page, setPage,
  } = useFilterState(STRATEGY_FILTERS);
  const [expandedBank, setExpandedBank] = useState<string | null>(null);
  const [selectedBanks, setSelectedBanks] = useState<ReadonlySet<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState<string | null>(null);
  const [isBulkRunning, setIsBulkRunning] = useState(false);
  const headerCheckboxRef = useRef<HTMLInputElement>(null);

  const queryString = toQueryString();
  const paginatedQuery = queryString
    ? `${queryString}&page=${page}&limit=${LIMIT}`
    : `page=${page}&limit=${LIMIT}`;

  const { data: paginatedData, isLoading, error } = useQuery({
    queryKey: ['strategies', queryString, page],
    queryFn: () => apiFetch<PaginatedResponse<Strategy>>(`/api/strategies?${paginatedQuery}`),
  });

  const data = paginatedData?.data;

  const { data: agentRuns } = useQuery({
    queryKey: ['agent-runs-latest'],
    queryFn: () => apiFetch<{ data: AgentRun[] }>('/api/agent-runs/latest').then(r => r.data),
    enabled: !data || data.length === 0,
  });

  const sorted = useMemo(
    () => data ? [...data].sort((a, b) => a.success_rate - b.success_rate) : [],
    [data],
  );

  const { totalBanks, avgSuccess, needAttention, healthyCount, degradedCount, deadCount } = useMemo(() => {
    const total = sorted.length;
    const avg = total > 0
      ? Math.round((sorted.reduce((sum, s) => sum + s.success_rate, 0) / total) * 100)
      : 0;
    const attention = sorted.filter(s => s.success_rate === 0).length;
    const healthy = sorted.filter(s => s.success_rate >= 0.7).length;
    const degraded = sorted.filter(s => s.success_rate >= 0.3 && s.success_rate < 0.7).length;
    const dead = sorted.filter(s => s.success_rate < 0.3).length;
    return { totalBanks: total, avgSuccess: avg, needAttention: attention, healthyCount: healthy, degradedCount: degraded, deadCount: dead };
  }, [sorted]);

  const updateHeaderCheckbox = useCallback((selected: ReadonlySet<string>, total: number) => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.checked = selected.size === total && total > 0;
      headerCheckboxRef.current.indeterminate = selected.size > 0 && selected.size < total;
    }
  }, []);

  const toggleBank = (bankCode: string) => {
    const next = new Set(selectedBanks);
    if (next.has(bankCode)) {
      next.delete(bankCode);
    } else {
      next.add(bankCode);
    }
    setSelectedBanks(next);
    updateHeaderCheckbox(next, sorted.length);
  };

  const toggleAll = () => {
    if (selectedBanks.size === sorted.length) {
      setSelectedBanks(new Set());
      updateHeaderCheckbox(new Set(), sorted.length);
    } else {
      const all = new Set(sorted.map(s => s.bank_code));
      setSelectedBanks(all);
      updateHeaderCheckbox(all, sorted.length);
    }
  };

  const selectAllFailing = () => {
    const failing = new Set(sorted.filter(s => s.success_rate === 0).map(s => s.bank_code));
    setSelectedBanks(failing);
    updateHeaderCheckbox(failing, sorted.length);
  };

  const clearSelection = () => {
    setSelectedBanks(new Set());
    updateHeaderCheckbox(new Set(), sorted.length);
  };

  const bulkRebuild = async () => {
    setIsBulkRunning(true);
    setBulkStatus('Rebuilding all selected banks...');
    try {
      const resp = await apiPost<{ queued: string[]; total_banks: number; failed: string[] }>(
        '/api/strategies/rebuild-all'
      );
      if (resp.failed?.length > 0) {
        toast.error(`Failed to queue: ${resp.failed.join(', ')}`);
      }
      toast.success(`Queued rebuild for ${resp.queued?.length ?? 0} banks`);
      clearSelection();
    } catch {
      toast.error('Failed to trigger rebuild');
    }
    setIsBulkRunning(false);
    setBulkStatus(null);
  };

  if (isLoading) return <p className="text-text-muted">Loading strategies...</p>;

  if (error) {
    return (
      <div className="text-error">
        <p>Failed to load strategies: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    const lastRun = agentRuns?.find(r => r.agent_name === 'strategist');
    return (
      <div>
        <h2 className="text-2xl font-bold text-text-heading mb-6">Strategies</h2>
        <div className="bg-bg-card rounded-lg border border-border p-6">
          <p className="text-text-muted mb-3">No strategies found.</p>
          {lastRun ? (
            <div className="text-sm space-y-1 mb-4">
              <p className="text-text-secondary">
                Last strategist run:{' '}
                <span className={lastRun.status === 'success' ? 'text-success' : lastRun.status === 'failed' ? 'text-error' : 'text-warning'}>
                  {lastRun.status.toUpperCase()}
                </span>
                {' '}at {formatShortDateTime(lastRun.started_at)}
              </p>
              {lastRun.error_message && (
                <p className="text-error text-xs font-[var(--font-mono)]">
                  Error: {lastRun.error_message}
                </p>
              )}
            </div>
          ) : (
            <p className="text-text-dim text-sm mb-4">Strategist has never been run.</p>
          )}
          <CrawlButton agent="strategist" label="Run Strategist" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-text-heading">Strategies</h2>
        <CrawlButton agent="strategist" label="Run All Strategist" />
      </div>

      <FilterBar
        config={STRATEGY_FILTERS}
        filters={filters}
        onFilterChange={setFilter}
        onFilterChangeBatch={setFilters}
        onClearAll={clearAll}
        onClearFilter={clearFilter}
        activeCount={activeCount}
        pageKey="strategies"
        totalResults={paginatedData?.total}
      />

      <SummaryStrip items={[
        { label: 'healthy', value: healthyCount, color: 'green' },
        { label: 'degraded', value: degradedCount, color: 'yellow' },
        { label: 'dead', value: deadCount, color: 'red' },
        { label: `banks (${avgSuccess}% avg success)`, value: totalBanks, color: 'blue' },
      ]} />

      {/* Bulk action bar — visible when banks selected OR status message showing */}
      {(selectedBanks.size > 0 || bulkStatus) && (
        <div className="flex items-center gap-3 mb-3 px-4 py-2.5 bg-bg-card rounded-lg border border-border-light">
          {bulkStatus ? (
            <span className="text-sm text-text-muted font-[var(--font-mono)]">{bulkStatus}</span>
          ) : (
            <>
              <span className="text-sm text-text-secondary">
                {selectedBanks.size} bank{selectedBanks.size > 1 ? 's' : ''} selected
              </span>
              <button
                onClick={bulkRebuild}
                disabled={isBulkRunning}
                className="px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent text-white hover:bg-accent/80 disabled:opacity-50"
              >
                Rebuild Selected
              </button>
              <button
                onClick={clearSelection}
                className="px-3 py-1.5 rounded-md text-[12px] font-medium text-text-muted hover:text-text-body"
              >
                Clear
              </button>
            </>
          )}
        </div>
      )}

      <div className="bg-bg-card rounded-lg border border-border">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="w-10 px-3 py-3">
                <input
                  ref={headerCheckboxRef}
                  type="checkbox"
                  onChange={toggleAll}
                  className="rounded border-border-light accent-accent"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bank</th>
              <th className="w-28 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Status</th>
              <th className="w-24 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Anti-Bot</th>
              <th className="w-24 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Trend</th>
              <th className="w-24 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((strategy) => {
              const isExpanded = expandedBank === strategy.bank_code;
              return (
                <Fragment key={strategy.bank_code}>
                  <tr
                    className="hover:bg-bg-hover cursor-pointer transition-colors"
                    onClick={() => setExpandedBank(isExpanded ? null : strategy.bank_code)}
                  >
                    <td className="w-10 px-3 py-3" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedBanks.has(strategy.bank_code)}
                        onChange={() => toggleBank(strategy.bank_code)}
                        className="rounded border-border-light accent-accent"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] text-text-dim transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▶</span>
                        <div>
                          <p className="text-sm font-[var(--font-mono)] font-medium text-text-heading">{strategy.bank_code}</p>
                          <p className="text-xs text-text-muted">{strategy.bank_name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="w-28 px-4 py-3"><StatusPill rate={strategy.success_rate} /></td>
                    <td className="w-24 px-4 py-3"><AntiBotBadge type={strategy.anti_bot_type} /></td>
                    <td className="px-4 py-3">
                      {strategy.success_trend && strategy.success_trend.length > 1 ? (
                        <SparklineBar
                          data={strategy.success_trend}
                          color={strategy.success_rate >= 0.7 ? '#4ade80' : strategy.success_rate >= 0.3 ? '#fbbf24' : '#f87171'}
                          height={20}
                        />
                      ) : (
                        <span className="text-text-dim text-xs">—</span>
                      )}
                    </td>
                    <td className="w-24 px-4 py-3 text-sm text-text-muted">{formatShortDateTime(strategy.updated_at)}</td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-bg-hover/50">
                      <td colSpan={6} className="px-12 py-4">
                        <div className="flex items-start justify-between">
                          <div className="space-y-2">
                            <div className="flex items-center gap-4 text-sm">
                              <span className="text-text-muted">Bypass:</span>
                              <span className="text-text-secondary font-[var(--font-mono)]">{strategy.bypass_method}</span>
                              <span className="text-text-muted">Version:</span>
                              <span className="text-text-secondary font-[var(--font-mono)]">v{strategy.version}</span>
                            </div>
                            <SuccessRateBar rate={strategy.success_rate} />
                          </div>
                          <div className="flex gap-2">
                            <CrawlButton agent="strategist" label="Rebuild Strategy" bank={strategy.bank_code} variant="secondary" />
                            <CrawlButton agent="lab" label="Test with Lab" bank={strategy.bank_code} variant="secondary" />
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {paginatedData && paginatedData.total > LIMIT && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-[12px] text-text-muted">
            Showing {(page - 1) * LIMIT + 1}-{Math.min(page * LIMIT, paginatedData.total)} of {paginatedData.total}
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
              Page {page} of {Math.ceil(paginatedData.total / LIMIT)}
            </span>
            <button
              className="px-3 py-1 text-[12px] border border-border rounded-md text-text-secondary disabled:opacity-50 hover:bg-bg-hover"
              disabled={page >= Math.ceil(paginatedData.total / LIMIT)}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Quick actions */}
      {needAttention > 0 && selectedBanks.size === 0 && (
        <button
          onClick={selectAllFailing}
          className="mt-3 text-xs text-text-dim hover:text-text-muted transition-colors"
        >
          Select all {needAttention} failing banks →
        </button>
      )}
    </div>
  );
}

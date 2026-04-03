import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, apiPost } from '../api/client';
import type { ExtendedDashboard, AlertsResponse, ChangesResponse, QualityResponse, HeatmapBank } from '../types/dashboard';
import { useCrawlStatus } from '../context/CrawlStatusContext';
import HealthBar from '../components/HealthBar';
import KpiCard from '../components/KpiCard';
import AlertItem from '../components/AlertItem';
import CompletenessBar from '../components/CompletenessBar';
import ConfidenceDots from '../components/ConfidenceDots';
import TrendChip from '../components/TrendChip';
import { SkeletonCard, SkeletonTable, SkeletonPanel } from '../components/Skeleton';

// ── Constants ────────────────────────────────────────────────────────────────

const LOAN_TABS = ['KPR', 'KPA', 'MULTIGUNA', 'KENDARAAN', 'ALL'] as const;
type LoanTab = (typeof LOAN_TABS)[number];

const ALERT_ICONS: Record<string, string> = {
  crawl_failure_unreachable: '🔴',
  crawl_failure_anti_bot: '🛡️',
  rate_anomaly: '📉',
  data_quality: '⚠️',
  stale_data: '🕐',
  strategy_health: '⚙️',
};

const CHANGE_BADGES: Record<string, { bg: string; text: string; label: string }> = {
  new_programs: { bg: 'bg-success/10', text: 'text-success', label: 'NEW' },
  rate_decrease: { bg: 'bg-running/10', text: 'text-running', label: 'RATE' },
  rate_increase: { bg: 'bg-running/10', text: 'text-running', label: 'RATE' },
  status_change: { bg: 'bg-error/10', text: 'text-error', label: 'ALERT' },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function getAlertIcon(category: string, type: string): string {
  const key = `${category}_${type}`;
  return ALERT_ICONS[key] ?? ALERT_ICONS[category] ?? '⚠️';
}

function getRateColorClass(rate: number | null): string {
  if (rate === null) return 'text-text-dim';
  if (rate < 6) return 'text-success';
  if (rate <= 8) return 'text-warning';
  return 'text-error';
}

function getMinRate(rates: Record<string, number | null>): number | null {
  const values = Object.values(rates).filter((v): v is number => v !== null);
  return values.length > 0 ? Math.min(...values) : null;
}

function getMaxRate(rates: Record<string, number | null>): number | null {
  const values = Object.values(rates).filter((v): v is number => v !== null);
  return values.length > 0 ? Math.max(...values) : null;
}

function formatRate(rate: number | null): string {
  return rate !== null ? `${rate.toFixed(2)}%` : '—';
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusDot({ status }: { readonly status: string }) {
  const colorClass =
    status === 'active' ? 'bg-success' :
    status === 'blocked' ? 'bg-error' :
    'bg-warning';
  return <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${colorClass}`} />;
}

interface RateTableProps {
  readonly banks: readonly HeatmapBank[];
}

function RateTable({ banks }: RateTableProps) {
  if (banks.length === 0) {
    return (
      <div className="flex items-center justify-center py-10 text-text-muted text-sm">
        No data available for this loan type.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border-light">
            <th className="text-left py-2 px-3 text-text-muted font-medium">Bank</th>
            <th className="text-right py-2 px-3 text-text-muted font-medium">Min Rate</th>
            <th className="text-right py-2 px-3 text-text-muted font-medium">Max Rate</th>
            <th className="text-center py-2 px-3 text-text-muted font-medium">7d Trend</th>
            <th className="text-left py-2 px-3 text-text-muted font-medium">Completeness</th>
            <th className="text-left py-2 px-3 text-text-muted font-medium">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {banks.map((bank) => {
            const minRate = getMinRate(bank.rates);
            const maxRate = getMaxRate(bank.rates);
            return (
              <tr key={bank.bank_code} className="border-b border-border-light/50 hover:bg-bg-hover/30">
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <StatusDot status={bank.website_status} />
                    <span className="font-medium text-text-heading truncate max-w-[120px]" title={bank.bank_name}>
                      {bank.bank_name}
                    </span>
                  </div>
                </td>
                <td className={`py-2 px-3 text-right font-[var(--font-mono)] ${getRateColorClass(minRate)}`}>
                  {formatRate(minRate)}
                </td>
                <td className={`py-2 px-3 text-right font-[var(--font-mono)] ${getRateColorClass(maxRate)}`}>
                  {formatRate(maxRate)}
                </td>
                <td className="py-2 px-3 text-center">
                  {bank.trend_7d != null && !isNaN(bank.trend_7d) ? (
                    <TrendChip value={bank.trend_7d} />
                  ) : (
                    <span className="text-text-dim">—</span>
                  )}
                </td>
                <td className="py-2 px-3">
                  <CompletenessBar score={bank.completeness_score} width={56} />
                </td>
                <td className="py-2 px-3">
                  <ConfidenceDots score={bank.data_confidence} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Overview() {
  const queryClient = useQueryClient();
  const { currentStep, steps, isRunning } = useCrawlStatus();

  const [activeTab, setActiveTab] = useState<LoanTab>('KPR');

  // Zone 2 data
  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<ExtendedDashboard>('/api/dashboard'),
    staleTime: 30_000,
  });

  // Zone 4 panels data
  const { data: alertsData, isLoading: alertsLoading } = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () => apiFetch<AlertsResponse>('/api/dashboard/alerts'),
    staleTime: 30_000,
  });

  const { data: changesData, isLoading: changesLoading } = useQuery({
    queryKey: ['dashboard-changes'],
    queryFn: () => apiFetch<ChangesResponse>('/api/dashboard/changes'),
    staleTime: 30_000,
  });

  const { data: qualityData, isLoading: qualityLoading } = useQuery({
    queryKey: ['dashboard-quality'],
    queryFn: () => apiFetch<QualityResponse>('/api/dashboard/quality'),
    staleTime: 30_000,
  });

  // Zone 3 data
  const { data: heatmapData, isLoading: heatmapLoading } = useQuery({
    queryKey: ['heatmap', activeTab],
    queryFn: () => apiFetch<{ banks: HeatmapBank[] }>(`/api/rates/heatmap?loan_type=${activeTab}`).then(r => r.banks),
    staleTime: 30_000,
  });

  // Alert action mutation
  const triggerAction = useMutation({
    mutationFn: (params: { agent: string; bankCodes: string[] }) =>
      Promise.all(params.bankCodes.map((code) => apiPost(`/api/crawl/${params.agent}?bank=${code}`))),
    onSuccess: () => {
      toast.success('Action triggered');
      void queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
    },
    onError: () => {
      toast.error('Failed to trigger action');
    },
  });

  // Pipeline progress string
  const runningStep = steps.find((s) => s.status === 'running');
  const pipelineProgress = runningStep?.bankCount != null && runningStep?.bankTotal != null
    ? `${runningStep.bankCount}/${runningStep.bankTotal}`
    : null;

  // Zone 3 quality bar totals for proportional display
  const qualityTotal = qualityData
    ? (qualityData.high.count + qualityData.medium.count + qualityData.low.count) || 1
    : 1;

  return (
    <div className="space-y-0">
      {/* Zone 1: HealthBar */}
      <HealthBar
        banksByStatus={dashboard?.banks_by_status ?? {}}
        pipelineStep={isRunning ? (currentStep ?? 'running') : null}
        pipelineProgress={pipelineProgress}
        successRate={dashboard?.success_rate ?? 0}
      />

      <div className="p-5 space-y-5">
        {/* Action Buttons */}
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-text-heading">Overview</h1>
          <div className="flex gap-2">
            <button
              onClick={() => apiPost('/api/crawl/daily').then(() => toast.success('Crawl All Banks triggered')).catch(() => toast.error('Failed to trigger crawl'))}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-error/10 text-error border border-error/20 hover:bg-error/20"
            >
              Crawl All Banks
            </button>
            <button
              onClick={() => apiPost('/api/crawl/scout').then(() => toast.success('Scout triggered')).catch(() => toast.error('Failed to trigger scout'))}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-card text-text-dim border border-border-light hover:bg-bg-hover"
            >
              Scout
            </button>
            <button
              onClick={() => apiPost('/api/crawl/learning').then(() => toast.success('Learning triggered')).catch(() => toast.error('Failed to trigger learning'))}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-bg-card text-text-dim border border-border-light hover:bg-bg-hover"
            >
              Learning
            </button>
          </div>
        </div>

        {/* Zone 2: KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {dashLoading ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : (
            <>
              <KpiCard
                title="Banks Monitored"
                value={dashboard?.total_banks ?? 0}
                delta={`+${dashboard?.deltas.banks_week ?? 0} this week`}
                deltaDirection="up"
                sparkline={dashboard?.sparklines.banks as number[]}
                sparklineColor="#4ade80"
              />
              <KpiCard
                title="Loan Programs"
                value={dashboard?.total_programs ?? 0}
                delta={`+${dashboard?.deltas.programs_new ?? 0} new`}
                deltaDirection="up"
                sparkline={dashboard?.sparklines.programs as number[]}
                sparklineColor="#60a5fa"
              />
              <KpiCard
                title="Avg KPR Rate"
                value={`${(dashboard?.sparklines.kpr_rate.at(-1) ?? 0).toFixed(1)}%`}
                delta={`${(dashboard?.deltas.kpr_rate_change ?? 0) > 0 ? '↑' : '↓'} ${Math.abs(dashboard?.deltas.kpr_rate_change ?? 0).toFixed(1)}%`}
                deltaDirection={(dashboard?.deltas.kpr_rate_change ?? 0) <= 0 ? 'up' : 'down'}
                sparkline={dashboard?.sparklines.kpr_rate as number[]}
                sparklineColor="#4ade80"
              />
              <KpiCard
                title="Data Quality"
                value={`${Math.round(((dashboard?.quality_avg as unknown as { avg_completeness?: number })?.avg_completeness ?? 0) * 100)}%`}
                delta="avg completeness"
                deltaDirection="neutral"
                sparkline={dashboard?.sparklines.quality as number[]}
                sparklineColor="#60a5fa"
              />
            </>
          )}
        </div>

        {/* Zone 3 + 4: Rate Table + Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-5">
          {/* Zone 3: Rate Intelligence Table */}
          <div className="bg-bg-card rounded-xl border border-border-light overflow-hidden">
            <div className="px-4 py-3 border-b border-border-light flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text-heading">Rate Intelligence</h2>
              <div className="flex gap-1">
                {LOAN_TABS.map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={[
                      'px-2.5 py-1 rounded text-[11px] font-medium transition-colors',
                      activeTab === tab
                        ? 'bg-accent text-white'
                        : 'text-text-muted hover:text-text-dim hover:bg-bg-hover',
                    ].join(' ')}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>
            {heatmapLoading ? (
              <div className="p-4">
                <SkeletonTable rows={6} />
              </div>
            ) : (
              <RateTable banks={heatmapData ?? []} />
            )}
          </div>

          {/* Zone 4: Right Sidebar */}
          <div className="space-y-4">
            {/* Needs Attention Panel */}
            <div className="bg-bg-card rounded-xl border border-border-light overflow-hidden">
              <div className="px-4 py-3 border-b border-border-light">
                <h3 className="text-sm font-semibold text-text-heading">Needs Attention</h3>
              </div>
              {alertsLoading ? (
                <div className="p-4">
                  <SkeletonPanel />
                </div>
              ) : alertsData && alertsData.alerts.length > 0 ? (
                <div>
                  {alertsData.alerts.map((alert, idx) => (
                    <AlertItem
                      key={idx}
                      icon={getAlertIcon(alert.category, alert.type)}
                      message={alert.message}
                      category={alert.category}
                      ctaLabel={alert.cta.label}
                      loading={triggerAction.isPending}
                      onAction={() =>
                        triggerAction.mutate({
                          agent: alert.cta.agent,
                          bankCodes: alert.bank_codes as string[],
                        })
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="px-4 py-6 text-center">
                  <span className="text-lg">✅</span>
                  <p className="text-xs text-text-muted mt-1">All clear — no issues detected</p>
                </div>
              )}
            </div>

            {/* Today's Changes Panel */}
            <div className="bg-bg-card rounded-xl border border-border-light overflow-hidden">
              <div className="px-4 py-3 border-b border-border-light">
                <h3 className="text-sm font-semibold text-text-heading">Today's Changes</h3>
              </div>
              {changesLoading ? (
                <div className="p-4">
                  <SkeletonPanel />
                </div>
              ) : changesData && changesData.changes.length > 0 ? (
                <div className="divide-y divide-border-light/50">
                  {changesData.changes.map((change, idx) => {
                    const badge = CHANGE_BADGES[change.type] ?? {
                      bg: 'bg-bg-hover',
                      text: 'text-text-dim',
                      label: 'INFO',
                    };
                    return (
                      <div key={idx} className="flex items-center gap-3 px-4 py-2.5">
                        <span
                          className={`flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded ${badge.bg} ${badge.text}`}
                        >
                          {badge.label}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-[11px] text-text-dim truncate">{change.detail}</p>
                        </div>
                        <span className="flex-shrink-0 text-[10px] text-text-muted font-[var(--font-mono)]">
                          ×{change.count}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="px-4 py-5 text-center">
                  <p className="text-xs text-text-muted">No changes yet today</p>
                </div>
              )}
            </div>

            {/* Quality Summary Panel */}
            <div className="bg-bg-card rounded-xl border border-border-light overflow-hidden">
              <div className="px-4 py-3 border-b border-border-light">
                <h3 className="text-sm font-semibold text-text-heading">Quality Summary</h3>
              </div>
              {qualityLoading ? (
                <div className="p-4">
                  <SkeletonPanel />
                </div>
              ) : qualityData ? (
                <div className="px-4 py-3 space-y-3">
                  {/* High */}
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-text-muted w-12 flex-shrink-0">High</span>
                    <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
                      <div
                        className="h-full rounded-full bg-success"
                        style={{ width: `${(qualityData.high.count / qualityTotal) * 100}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-text-dim w-6 text-right font-[var(--font-mono)]">
                      {qualityData.high.count}
                    </span>
                  </div>
                  {/* Medium */}
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-text-muted w-12 flex-shrink-0">Medium</span>
                    <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
                      <div
                        className="h-full rounded-full bg-warning"
                        style={{ width: `${(qualityData.medium.count / qualityTotal) * 100}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-text-dim w-6 text-right font-[var(--font-mono)]">
                      {qualityData.medium.count}
                    </span>
                  </div>
                  {/* Low */}
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-text-muted w-12 flex-shrink-0">Low</span>
                    <div className="flex-1 h-2 rounded-full bg-bg-hover overflow-hidden">
                      <div
                        className="h-full rounded-full bg-error"
                        style={{ width: `${(qualityData.low.count / qualityTotal) * 100}%` }}
                      />
                    </div>
                    <span className="text-[11px] text-text-dim w-6 text-right font-[var(--font-mono)]">
                      {qualityData.low.count}
                    </span>
                  </div>
                  <p className="text-[10px] text-text-muted pt-1">
                    Avg completeness: {Math.round((qualityData.avg_completeness ?? 0) * 100)}%
                  </p>
                </div>
              ) : (
                <div className="px-4 py-5 text-center">
                  <p className="text-xs text-text-muted">No quality data available</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import CrawlButton from '../components/CrawlButton';
import RateHeatmap, { type HeatmapBank } from '../components/RateHeatmap';
import LiveFeed from '../components/LiveFeed';
import SparklineChart from '../components/SparklineChart';
import RingChart from '../components/RingChart';

interface DashboardData {
  total_banks: number;
  total_programs: number;
  banks_by_status: Record<string, number>;
  success_rate: number;
  crawl_stats: {
    total_crawls: number;
    successful: number;
    failed: number;
    blocked: number;
    timed_out: number;
    total_programs_found: number;
    total_programs_new: number;
    avg_duration_ms: number;
  };
}

interface TrendData {
  loan_type: string;
  series: { date: string; avg_min_rate: number }[];
}

interface HeatmapResponse {
  banks: HeatmapBank[];
}

function MetricCard({
  title, value, delta, children, valueClassName,
}: {
  readonly title: string;
  readonly value: string | number;
  readonly delta?: string;
  readonly children?: React.ReactNode;
  readonly valueClassName?: string;
}) {
  return (
    <div className="bg-bg-card border border-border rounded-xl p-5 relative overflow-hidden min-w-0">
      <p className="text-[11px] text-text-muted uppercase tracking-wide mb-1.5">{title}</p>
      <p className={`text-[28px] font-bold font-[var(--font-mono)] text-text-heading${valueClassName ? ` ${valueClassName}` : ''}`}>{value}</p>
      {delta && (
        <p className={`text-[11px] mt-1 ${delta.startsWith('↑') ? 'text-success' : delta.startsWith('↓') ? 'text-error' : 'text-text-muted'}`}>
          {delta}
        </p>
      )}
      {children}
    </div>
  );
}

export default function Overview() {
  const { eventBuffer } = useWebSocket();

  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardData>('/api/dashboard'),
  });

  const { data: heatmap } = useQuery({
    queryKey: ['rates-heatmap'],
    queryFn: () => apiFetch<HeatmapResponse>('/api/rates/heatmap'),
  });

  const { data: trend } = useQuery({
    queryKey: ['rates-trend'],
    queryFn: () => apiFetch<TrendData>('/api/rates/trend?loan_type=KPR&days=7'),
  });

  if (dashLoading || !dashboard) {
    return <p className="text-text-muted">Loading dashboard...</p>;
  }

  const stats = dashboard.crawl_stats;
  const successRate = stats.total_crawls > 0
    ? Math.round((stats.successful / stats.total_crawls) * 100)
    : 0;
  const activeCount = dashboard.banks_by_status?.active ?? 0;
  const unreachableCount = dashboard.banks_by_status?.unreachable ?? 0;
  const blockedCount = dashboard.banks_by_status?.blocked ?? 0;

  const sparklineData = (trend?.series ?? []).map((s) => ({
    date: s.date,
    value: s.avg_min_rate,
  }));
  const latestRate = sparklineData.length > 0 ? sparklineData[sparklineData.length - 1].value : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-text-heading">Overview</h2>
        <div className="flex gap-2">
          <CrawlButton agent="daily" label="Crawl All Banks" />
          <CrawlButton agent="scout" label="Scout" variant="secondary" />
          <CrawlButton agent="learning" label="Learning" variant="secondary" />
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Banks Monitored"
          value={dashboard.total_banks}
          delta={`${activeCount} active · ${unreachableCount} unreachable · ${blockedCount} blocked`}
        />
        <MetricCard
          title="Loan Programs"
          value={dashboard.total_programs}
          delta={stats.total_programs_new > 0 ? `↑ ${stats.total_programs_new} new this week` : undefined}
        />
        <MetricCard
          title="Avg. KPR Rate"
          value={latestRate != null ? `${latestRate.toFixed(1)}%` : 'N/A'}
        >
          <SparklineChart data={sparklineData} />
        </MetricCard>
        <MetricCard
          title="Success Rate (7d)"
          value={`${successRate}%`}
          delta={stats.failed > 0 ? `${stats.failed} failed` : undefined}
          valueClassName="pr-14"
        >
          <div className="absolute top-4 right-4">
            <RingChart
              value={successRate}
              color={successRate >= 70 ? '#34d399' : successRate >= 40 ? '#fbbf24' : '#f87171'}
            />
          </div>
        </MetricCard>
      </div>

      {/* Heatmap + Live Feed */}
      <div className="grid grid-cols-[1fr_320px] gap-5">
        <RateHeatmap banks={heatmap?.banks ?? []} />
        <LiveFeed events={eventBuffer} />
      </div>
    </div>
  );
}

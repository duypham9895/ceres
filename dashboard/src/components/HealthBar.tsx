import clsx from 'clsx';

interface HealthBarProps {
  readonly banksByStatus: Record<string, number>;
  readonly pipelineStep?: string | null;
  readonly pipelineProgress?: string | null;
  readonly successRate: number;
  readonly successRateTrend?: number;
}

export default function HealthBar({ banksByStatus, pipelineStep, pipelineProgress, successRate, successRateTrend }: HealthBarProps) {
  const active = banksByStatus.active ?? 0;
  const unreachable = banksByStatus.unreachable ?? 0;
  const blocked = banksByStatus.blocked ?? 0;
  const successPct = Math.round(successRate * 100);
  const trendStr = successRateTrend != null
    ? (successRateTrend > 0 ? `↑${Math.abs(successRateTrend).toFixed(0)}%` : successRateTrend < 0 ? `↓${Math.abs(successRateTrend).toFixed(0)}%` : '')
    : '';

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-2 bg-bg-card/50 border-b border-border-light text-xs">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-success" />{active} active</span>
        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-warning" />{unreachable} unreachable</span>
        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-error" />{blocked} blocked</span>
      </div>
      {pipelineStep && (
        <span className="text-running hidden md:inline">
          ▶ {pipelineStep} {pipelineProgress ? `— ${pipelineProgress}` : ''}
        </span>
      )}
      <span className={clsx('font-medium', successPct >= 70 ? 'text-success' : successPct >= 40 ? 'text-warning' : 'text-error')}>
        {successPct}% success (7d) {trendStr}
      </span>
    </div>
  );
}

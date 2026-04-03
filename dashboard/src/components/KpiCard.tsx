import SparklineBar from './SparklineBar';
import clsx from 'clsx';

interface KpiCardProps {
  readonly title: string;
  readonly value: string | number;
  readonly delta?: string;
  readonly deltaDirection?: 'up' | 'down' | 'neutral';
  readonly sparkline?: number[];
  readonly sparklineColor?: string;
}

export default function KpiCard({
  title, value, delta, deltaDirection = 'neutral', sparkline, sparklineColor,
}: KpiCardProps) {
  return (
    <div className="bg-bg-card rounded-xl p-5 border border-border-light">
      <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">{title}</p>
      <p className="text-2xl font-bold mt-1 font-[var(--font-mono)] text-text-heading">{value}</p>
      {delta && (
        <p className={clsx(
          'text-[11px] mt-1',
          deltaDirection === 'up' && 'text-success',
          deltaDirection === 'down' && 'text-error',
          deltaDirection === 'neutral' && 'text-text-dim',
        )}>
          {delta}
        </p>
      )}
      {sparkline && sparkline.length > 1 && (
        <div className="mt-2">
          <SparklineBar data={sparkline} color={sparklineColor} height={24} />
        </div>
      )}
    </div>
  );
}

import clsx from 'clsx';

interface CompletenessBarProps {
  readonly score: number; // 0-1
  readonly width?: number; // px, default 60
}

export default function CompletenessBar({ score, width = 60 }: CompletenessBarProps) {
  const pct = Math.round(score * 100);
  const colorClass = score > 0.8 ? 'bg-success' : score >= 0.5 ? 'bg-warning' : 'bg-error';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 rounded-full bg-bg-hover overflow-hidden" style={{ width }}>
        <div className={clsx('h-full rounded-full', colorClass)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-text-dim">{pct}%</span>
    </div>
  );
}

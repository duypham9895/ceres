interface StatsCardProps {
  readonly title: string;
  readonly value: string | number;
  readonly subtitle?: string;
  readonly color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray';
}

const COLOR_MAP = {
  blue: 'border-running/30',
  green: 'border-success/30',
  red: 'border-error/30',
  yellow: 'border-warning/30',
  gray: 'border-border-light',
};

export default function StatsCard({ title, value, subtitle, color = 'blue' }: StatsCardProps) {
  return (
    <div className={`bg-bg-card rounded-xl p-5 border ${COLOR_MAP[color]}`}>
      <p className="text-[11px] font-medium text-text-muted uppercase tracking-wide">{title}</p>
      <p className="text-2xl font-bold mt-1 font-[var(--font-mono)] text-text-heading">{value}</p>
      {subtitle && <p className="text-[11px] mt-1 text-text-dim">{subtitle}</p>}
    </div>
  );
}

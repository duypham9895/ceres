import type { ReactNode } from 'react';

interface SummaryStripItem {
  readonly label: string;
  readonly value: number;
  readonly color: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}

interface SummaryStripProps {
  readonly items: SummaryStripItem[];
  readonly actions?: ReactNode;
}

const DOT_COLORS = {
  green: 'bg-success',
  yellow: 'bg-warning',
  red: 'bg-error',
  blue: 'bg-running',
  gray: 'bg-text-dim',
};

export default function SummaryStrip({ items, actions }: SummaryStripProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 bg-bg-card rounded-lg border border-border-light mb-4">
      <div className="flex flex-wrap items-center gap-4">
        {items.map((item) => (
          <span key={item.label} className="flex items-center gap-1.5 text-xs text-text-dim">
            <span className={`w-2 h-2 rounded-full ${DOT_COLORS[item.color]}`} />
            {item.value} {item.label}
          </span>
        ))}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

import { Loader2 } from 'lucide-react';
import clsx from 'clsx';

interface AlertItemProps {
  readonly icon: string;
  readonly message: string;
  readonly category: string;
  readonly ctaLabel: string;
  readonly onAction: () => void;
  readonly loading?: boolean;
}

export default function AlertItem({ icon, message, category, ctaLabel, onAction, loading = false }: AlertItemProps) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 border-b border-border-light last:border-b-0 hover:bg-bg-hover/50">
      <span className="text-sm flex-shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-text-dim truncate">{message}</p>
        <p className="text-[9px] text-text-muted uppercase tracking-wide">{category}</p>
      </div>
      <button
        onClick={onAction}
        disabled={loading}
        className={clsx(
          'flex-shrink-0 text-[10px] font-semibold px-2.5 py-1 rounded',
          'bg-accent/10 text-accent border border-accent/20',
          'hover:bg-accent/20 disabled:opacity-50',
        )}
      >
        {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : ctaLabel}
      </button>
    </div>
  );
}

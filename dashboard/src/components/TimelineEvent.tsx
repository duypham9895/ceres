import StatusBadge from './StatusBadge';
import { formatRelativeTime, formatDuration } from '../utils/format';

interface CrawlLog {
  readonly id: string;
  readonly started_at: string;
  readonly bank_code: string;
  readonly status: string;
  readonly duration_ms: number | null;
  readonly programs_found: number;
  readonly error_message: string | null;
}

const BORDER_COLORS: Record<string, string> = {
  success: 'border-l-success',
  failed: 'border-l-error',
  blocked: 'border-l-warning',
  timeout: 'border-l-error',
  partial: 'border-l-warning',
  running: 'border-l-running',
};

export default function TimelineEvent({ log }: { readonly log: CrawlLog }) {
  return (
    <div className={`flex items-start gap-3 px-4 py-3 border-l-2 ${BORDER_COLORS[log.status] ?? 'border-l-border'} hover:bg-bg-hover transition-colors`}>
      <div className="shrink-0 w-16 text-[11px] text-text-dim font-[var(--font-mono)]" title={log.started_at}>
        {formatRelativeTime(log.started_at)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-text-heading">{log.bank_code}</span>
          <StatusBadge status={log.status} />
          {log.duration_ms != null && (
            <span className="text-[10px] text-text-dim font-[var(--font-mono)]">
              {formatDuration(log.duration_ms)}
            </span>
          )}
          {log.programs_found > 0 && (
            <span className="text-[10px] text-success-dim">
              {log.programs_found} programs
            </span>
          )}
        </div>
        {log.error_message && (
          <p className="text-[11px] text-error-dim mt-1 truncate" title={log.error_message}>
            {log.error_message}
          </p>
        )}
      </div>
    </div>
  );
}

export type { CrawlLog };

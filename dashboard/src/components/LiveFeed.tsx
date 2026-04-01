import type { CrawlEvent } from '../hooks/useWebSocket';

const TYPE_COLORS: Record<string, string> = {
  job_finish: 'bg-success/15 text-success-dim',
  job_error: 'bg-error/15 text-error-dim',
  job_start: 'bg-running/15 text-running-dim',
  job_step_start: 'bg-running/15 text-running-dim',
  job_progress: 'bg-accent/15 text-accent-light',
};

function formatEventMessage(event: CrawlEvent): string {
  switch (event.type) {
    case 'job_start':
      return `Started ${event.agent ?? 'crawl'} job`;
    case 'job_step_start':
      return `Running ${event.step ?? 'step'}`;
    case 'job_progress': {
      const processed = event.banks_processed ?? 0;
      const total = event.banks_total ?? 0;
      return `${event.step ?? 'Step'}: ${processed}/${total} banks`;
    }
    case 'job_finish':
      return 'Crawl completed';
    case 'job_error':
      return event.error ?? 'Crawl failed';
    default:
      return event.type;
  }
}

export default function LiveFeed({ events }: { readonly events: readonly CrawlEvent[] }) {
  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden flex flex-col">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse-red" />
        <h3 className="text-[13px] font-semibold text-text-body">Live Activity</h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <p className="px-4 py-6 text-[12px] text-text-muted text-center">
            Waiting for crawl events...
          </p>
        ) : (
          events.map((event, i) => (
            <div
              key={`${event.job_id}-${event.type}-${i}`}
              className="px-4 py-2 flex items-center gap-2.5 text-[12px] border-b border-border/50 animate-feed-in"
            >
              <span className="text-accent-light font-medium text-[11px] shrink-0">
                {event.agent ?? event.step ?? 'system'}
              </span>
              <span className="text-text-secondary truncate flex-1">
                {formatEventMessage(event)}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${TYPE_COLORS[event.type] ?? 'bg-bg-hover text-text-muted'}`}>
                {event.type.replace('job_', '')}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

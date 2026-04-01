import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { formatShortDate } from '../utils/format';

interface Recommendation {
  readonly id: string;
  readonly rec_type: string;
  readonly title: string;
  readonly summary: string;
  readonly priority: number;
  readonly impact_score: number;
  readonly created_at: string;
}

const REC_TYPE_COLORS: Record<string, string> = {
  partnership_opportunity: 'bg-running/15 text-running-dim',
  product_gap: 'bg-warning/15 text-warning-dim',
  competitive_analysis: 'bg-success/15 text-success-dim',
  pricing: 'bg-accent/15 text-accent-light',
  market_trend: 'bg-success/15 text-success-dim',
};

function formatRecType(recType: string): string {
  return recType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function PriorityStars({ priority }: { readonly priority: number }) {
  const clamped = Math.max(1, Math.min(5, priority));
  return (
    <div className="flex gap-0.5" title={`Priority: ${clamped}/5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} className={i < clamped ? 'text-warning' : 'text-text-dim'}>
          ★
        </span>
      ))}
    </div>
  );
}

function ImpactBar({ score }: { readonly score: number }) {
  const percentage = Math.round(score * 100);
  const barColor = percentage >= 70 ? 'bg-success' : percentage >= 40 ? 'bg-warning' : 'bg-error';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-border rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm font-[var(--font-mono)] text-text-secondary w-10 text-right">{percentage}%</span>
    </div>
  );
}

function RecTypeBadge({ recType }: { readonly recType: string }) {
  const colorClass = REC_TYPE_COLORS[recType] ?? 'bg-border text-text-secondary';
  return (
    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
      {formatRecType(recType)}
    </span>
  );
}

export default function Recommendations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => apiFetch<{ data: Recommendation[] }>('/api/recommendations').then(r => r.data),
  });

  if (isLoading) return <p className="text-text-muted">Loading recommendations...</p>;

  if (error) {
    return (
      <div className="text-error">
        <p>Failed to load recommendations: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-text-heading mb-6">Recommendations</h2>
        <p className="text-text-muted">No recommendations yet. Run the Learning agent to generate insights.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-text-heading mb-6">Recommendations</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.map((rec) => (
          <div key={rec.id} className="bg-bg-card rounded-lg border border-border p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <RecTypeBadge recType={rec.rec_type} />
              <PriorityStars priority={rec.priority} />
            </div>
            <h3 className="text-lg font-semibold text-text-heading">{rec.title}</h3>
            <p className="text-sm text-text-secondary leading-relaxed">{rec.summary}</p>
            <div>
              <p className="text-xs text-text-muted mb-1">Impact Score</p>
              <ImpactBar score={rec.impact_score} />
            </div>
            <p className="text-xs text-text-dim mt-auto">{formatShortDate(rec.created_at)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

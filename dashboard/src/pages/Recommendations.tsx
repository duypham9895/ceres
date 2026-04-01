import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';

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
  partnership_opportunity: 'bg-blue-100 text-blue-800',
  product_gap: 'bg-orange-100 text-orange-800',
  competitive_analysis: 'bg-green-100 text-green-800',
  pricing: 'bg-purple-100 text-purple-800',
  market_trend: 'bg-teal-100 text-teal-800',
};

function formatRecType(recType: string): string {
  return recType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function PriorityStars({ priority }: { readonly priority: number }) {
  const clamped = Math.max(1, Math.min(5, priority));
  return (
    <div className="flex gap-0.5" title={`Priority: ${clamped}/5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} className={i < clamped ? 'text-yellow-400' : 'text-gray-300'}>
          ★
        </span>
      ))}
    </div>
  );
}

function ImpactBar({ score }: { readonly score: number }) {
  const percentage = Math.round(score * 100);
  const barColor = percentage >= 70 ? 'bg-green-500' : percentage >= 40 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm text-gray-600 w-10 text-right">{percentage}%</span>
    </div>
  );
}

function RecTypeBadge({ recType }: { readonly recType: string }) {
  const colorClass = REC_TYPE_COLORS[recType] ?? 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${colorClass}`}>
      {formatRecType(recType)}
    </span>
  );
}

export default function Recommendations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => apiFetch<Recommendation[]>('/api/recommendations'),
  });

  if (isLoading) return <p className="text-gray-500">Loading recommendations...</p>;

  if (error) {
    return (
      <div className="text-red-600">
        <p>Failed to load recommendations: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Recommendations</h2>
        <p className="text-gray-500">No recommendations yet. Run the Learning agent to generate insights.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Recommendations</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.map((rec) => (
          <div key={rec.id} className="bg-white rounded-lg shadow p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <RecTypeBadge recType={rec.rec_type} />
              <PriorityStars priority={rec.priority} />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">{rec.title}</h3>
            <p className="text-sm text-gray-600 leading-relaxed">{rec.summary}</p>
            <div>
              <p className="text-xs text-gray-500 mb-1">Impact Score</p>
              <ImpactBar score={rec.impact_score} />
            </div>
            <p className="text-xs text-gray-400 mt-auto">{formatDate(rec.created_at)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

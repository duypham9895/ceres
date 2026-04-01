import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import { formatShortDateTime } from '../utils/format';
import CrawlButton from '../components/CrawlButton';

interface Strategy {
  readonly bank_code: string;
  readonly bank_name: string;
  readonly bypass_method: string;
  readonly anti_bot_type: string | null;
  readonly success_rate: number;
  readonly version: number;
  readonly updated_at: string;
}

function SuccessRateBar({ rate }: { readonly rate: number }) {
  const percentage = Math.round(rate * 100);
  const barColor = percentage >= 80 ? 'bg-success' : percentage >= 50 ? 'bg-warning' : 'bg-error';

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-border rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm font-[var(--font-mono)] text-text-secondary">{percentage}%</span>
    </div>
  );
}

export default function Strategies() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiFetch<{ data: Strategy[] }>('/api/strategies').then(r => r.data),
  });

  if (isLoading) return <p className="text-text-muted">Loading strategies...</p>;

  if (error) {
    return (
      <div className="text-error">
        <p>Failed to load strategies: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-text-heading mb-6">Strategies</h2>
        <p className="text-text-muted">No strategies found. Run the Strategist agent to generate strategies.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-text-heading mb-6">Strategies</h2>
      <div className="overflow-x-auto bg-bg-card rounded-lg border border-border">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-bg-card">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bank Code</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bank Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bypass Method</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Anti-Bot Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Success Rate</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Version</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Updated</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-bg-card divide-y divide-border">
            {data.map((strategy) => (
              <tr key={strategy.bank_code} className="hover:bg-bg-hover">
                <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-heading">{strategy.bank_code}</td>
                <td className="px-4 py-3 text-sm text-text-heading">{strategy.bank_name}</td>
                <td className="px-4 py-3 text-sm text-text-secondary">{strategy.bypass_method}</td>
                <td className="px-4 py-3 text-sm text-text-secondary">{strategy.anti_bot_type || 'None'}</td>
                <td className="px-4 py-3"><SuccessRateBar rate={strategy.success_rate} /></td>
                <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">v{strategy.version}</td>
                <td className="px-4 py-3 text-sm text-text-muted">{formatShortDateTime(strategy.updated_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <CrawlButton agent="strategist" label="Rebuild Strategy" bank={strategy.bank_code} variant="secondary" />
                    <CrawlButton agent="lab" label="Test with Lab" bank={strategy.bank_code} variant="secondary" />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

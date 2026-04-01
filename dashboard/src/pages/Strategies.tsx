import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function SuccessRateBar({ rate }: { readonly rate: number }) {
  const percentage = Math.round(rate * 100);
  const barColor = percentage >= 80 ? 'bg-green-500' : percentage >= 50 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-gray-200 rounded-full h-2">
        <div className={`${barColor} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <span className="text-sm text-gray-600">{percentage}%</span>
    </div>
  );
}

export default function Strategies() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiFetch<{ data: Strategy[] }>('/api/strategies').then(r => r.data),
  });

  if (isLoading) return <p className="text-gray-500">Loading strategies...</p>;

  if (error) {
    return (
      <div className="text-red-600">
        <p>Failed to load strategies: {error instanceof Error ? error.message : 'Unknown error'}</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Strategies</h2>
        <p className="text-gray-500">No strategies found. Run the Strategist agent to generate strategies.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Strategies</h2>
      <div className="overflow-x-auto bg-white rounded-lg shadow">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bank Code</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bank Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bypass Method</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Anti-Bot Type</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Success Rate</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Version</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Updated</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data.map((strategy) => (
              <tr key={strategy.bank_code} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-mono text-gray-900">{strategy.bank_code}</td>
                <td className="px-4 py-3 text-sm text-gray-900">{strategy.bank_name}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{strategy.bypass_method}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{strategy.anti_bot_type || 'None'}</td>
                <td className="px-4 py-3"><SuccessRateBar rate={strategy.success_rate} /></td>
                <td className="px-4 py-3 text-sm text-gray-600">v{strategy.version}</td>
                <td className="px-4 py-3 text-sm text-gray-500">{formatDate(strategy.updated_at)}</td>
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

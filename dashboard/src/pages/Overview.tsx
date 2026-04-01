import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import StatsCard from '../components/StatsCard';
import CrawlButton from '../components/CrawlButton';

interface DashboardData {
  total_banks: number;
  banks_active: number;
  banks_unreachable: number;
  banks_blocked: number;
  total_programs: number;
  success_rate: number;
  total_crawls_7d: number;
  failures_7d: number;
}

export default function Overview() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardData>('/api/dashboard'),
  });

  if (isLoading || !data) return <p className="text-gray-500">Loading dashboard...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <div className="flex gap-3">
          <CrawlButton agent="daily" label="Crawl All Banks" />
          <CrawlButton agent="scout" label="Run Scout" variant="secondary" />
          <CrawlButton agent="learning" label="Run Learning" variant="secondary" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatsCard title="Total Banks" value={data.total_banks} subtitle={`${data.banks_active} active`} color="blue" />
        <StatsCard title="Loan Programs" value={data.total_programs} color="green" />
        <StatsCard title="Success Rate (7d)" value={`${Math.round(data.success_rate * 100)}%`} color={data.success_rate >= 0.7 ? 'green' : 'red'} />
        <StatsCard title="Crawls (7d)" value={data.total_crawls_7d} subtitle={`${data.failures_7d} failed`} color="gray" />
      </div>
    </div>
  );
}

import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import CrawlButton from '../components/CrawlButton';

interface BankInfo {
  id: number;
  bank_code: string;
  bank_name: string;
  bank_category: string;
  bank_type: string;
  website_url: string;
  website_status: string;
}

interface Strategy {
  bypass_method: string;
  success_rate: number;
  version: string;
}

interface LoanProgram {
  id: number;
  program_name: string;
  loan_type: string;
  interest_rate_min: number | null;
  interest_rate_max: number | null;
  last_updated_at: string;
}

interface CrawlLog {
  id: number;
  agent: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

interface BankDetailData {
  bank: BankInfo;
  strategy: Strategy | null;
  programs: LoanProgram[];
  crawl_logs: CrawlLog[];
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

function InfoItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{children}</dd>
    </div>
  );
}

export default function BankDetail() {
  const { id } = useParams<{ id: string }>();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['bank', id],
    queryFn: () => apiFetch<BankDetailData>(`/api/banks/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-gray-500">Loading bank details...</p>;
  if (isError) return <p className="text-red-500">Error: {error instanceof Error ? error.message : 'Failed to load bank'}</p>;
  if (!data) return null;

  const { bank, strategy, programs, crawl_logs } = data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">{bank.bank_name}</h2>
        <CrawlButton agent="daily" label="Crawl This Bank" bank={bank.bank_code} />
      </div>

      {/* Bank Info Card */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Bank Information</h3>
        <dl className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <InfoItem label="Code">{bank.bank_code}</InfoItem>
          <InfoItem label="Name">{bank.bank_name}</InfoItem>
          <InfoItem label="Category">{bank.bank_category}</InfoItem>
          <InfoItem label="Type">{bank.bank_type}</InfoItem>
          <InfoItem label="Website">
            <a href={bank.website_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              {bank.website_url}
            </a>
          </InfoItem>
          <InfoItem label="Status"><StatusBadge status={bank.website_status} /></InfoItem>
        </dl>
      </div>

      {/* Strategy Card */}
      {strategy && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Strategy</h3>
          <dl className="grid grid-cols-3 gap-4">
            <InfoItem label="Bypass Method">{strategy.bypass_method}</InfoItem>
            <InfoItem label="Success Rate">{Math.round(strategy.success_rate * 100)}%</InfoItem>
            <InfoItem label="Version">{strategy.version}</InfoItem>
          </dl>
        </div>
      )}

      {/* Loan Programs Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Loan Programs ({programs.length})</h3>
        </div>
        {programs.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">No loan programs found.</p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Program</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Interest Rate</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {programs.map((program) => (
                <tr key={program.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{program.program_name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{program.loan_type}</td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {program.interest_rate_min != null && program.interest_rate_max != null
                      ? `${program.interest_rate_min}% - ${program.interest_rate_max}%`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{formatDate(program.last_updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Crawl History Table */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Crawl History</h3>
        </div>
        {crawl_logs.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">No crawl logs found.</p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Finished</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {crawl_logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{log.agent}</td>
                  <td className="px-4 py-3 text-sm"><StatusBadge status={log.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-600">{formatDate(log.started_at)}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{formatDate(log.finished_at)}</td>
                  <td className="px-4 py-3 text-sm text-red-600">{log.error_message || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

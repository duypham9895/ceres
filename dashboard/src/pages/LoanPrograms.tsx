import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';

const LOAN_TYPES = [
  'KPR', 'KPA', 'KPT', 'MULTIGUNA', 'KENDARAAN', 'MODAL_KERJA',
  'INVESTASI', 'PENDIDIKAN', 'PMI', 'TAKE_OVER', 'REFINANCING', 'OTHER',
] as const;

const SORT_OPTIONS = [
  { value: 'program_name', label: 'Program Name' },
  { value: 'min_interest_rate', label: 'Min Interest Rate' },
  { value: 'data_confidence', label: 'Data Confidence' },
  { value: 'completeness_score', label: 'Completeness Score' },
] as const;

interface LoanProgram {
  readonly id: string;
  readonly program_name: string;
  readonly bank_code: string;
  readonly loan_type: string;
  readonly min_interest_rate: number | null;
  readonly max_interest_rate: number | null;
  readonly min_amount: number | null;
  readonly max_amount: number | null;
  readonly min_tenure_months: number | null;
  readonly max_tenure_months: number | null;
  readonly data_confidence: number;
  readonly completeness_score: number;
  readonly raw_data: Record<string, unknown> | null;
}

const LIMIT = 20;

function formatRange(min: number | null, max: number | null, suffix: string): string {
  if (min == null && max == null) return '-';
  if (min != null && max != null) return `${min}${suffix} - ${max}${suffix}`;
  if (min != null) return `${min}${suffix}+`;
  return `up to ${max}${suffix}`;
}

function formatAmount(value: number | null): string {
  if (value == null) return '';
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

function formatAmountRange(min: number | null, max: number | null): string {
  if (min == null && max == null) return '-';
  const minStr = formatAmount(min);
  const maxStr = formatAmount(max);
  if (min != null && max != null) return `${minStr} - ${maxStr}`;
  if (min != null) return `${minStr}+`;
  return `up to ${maxStr}`;
}

function ConfidenceBar({ value }: { readonly value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  );
}

export default function LoanPrograms() {
  const [page, setPage] = useState(1);
  const [loanType, setLoanType] = useState('');
  const [sort, setSort] = useState('program_name');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const queryParams = new URLSearchParams({
    page: String(page),
    limit: String(LIMIT),
    sort,
  });
  if (loanType) queryParams.set('loan_type', loanType);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['loan-programs', page, loanType, sort],
    queryFn: () =>
      apiFetch<PaginatedResponse<LoanProgram>>(`/api/loan-programs?${queryParams.toString()}`),
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Loan Programs</h2>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          value={loanType}
          onChange={(e) => { setLoanType(e.target.value); setPage(1); }}
        >
          <option value="">All Loan Types</option>
          {LOAN_TYPES.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>

        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          value={sort}
          onChange={(e) => { setSort(e.target.value); setPage(1); }}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-gray-500">Loading loan programs...</p>}
      {isError && <p className="text-red-600">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Program</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bank</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Interest Rate</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount Range</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tenure</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Completeness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.data.map((program) => (
                  <ProgramRow
                    key={program.id}
                    program={program}
                    isExpanded={expandedId === program.id}
                    onToggle={() => setExpandedId(expandedId === program.id ? null : program.id)}
                  />
                ))}
                {data.data.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                      No loan programs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-600">
              Showing {(page - 1) * LIMIT + 1}-{Math.min(page * LIMIT, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 text-sm border rounded disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <button
                className="px-3 py-1 text-sm border rounded disabled:opacity-50"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ProgramRow({
  program,
  isExpanded,
  onToggle,
}: {
  readonly program: LoanProgram;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="hover:bg-gray-50 cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-4 py-3 text-sm font-medium text-gray-900">{program.program_name}</td>
        <td className="px-4 py-3 text-sm text-gray-600">{program.bank_code}</td>
        <td className="px-4 py-3 text-sm">
          <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">
            {program.loan_type}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">
          {formatRange(program.min_interest_rate, program.max_interest_rate, '%')}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">
          {formatAmountRange(program.min_amount, program.max_amount)}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">
          {formatRange(program.min_tenure_months, program.max_tenure_months, ' mo')}
        </td>
        <td className="px-4 py-3 text-sm">
          <ConfidenceBar value={program.data_confidence} />
        </td>
        <td className="px-4 py-3 text-sm">
          <ConfidenceBar value={program.completeness_score} />
        </td>
      </tr>
      {isExpanded && program.raw_data && (
        <tr>
          <td colSpan={8} className="px-4 py-4 bg-gray-50">
            <pre className="text-xs text-gray-700 overflow-auto max-h-64 p-3 bg-white rounded border">
              {JSON.stringify(program.raw_data, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}

import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import { formatRange, formatAmountRange } from '../utils/format';

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

function ConfidencePill({ value }: { readonly value: number }) {
  const pct = Math.round(value * 100);
  const style = pct >= 80
    ? 'bg-success/20 text-success'
    : pct >= 50
      ? 'bg-warning/20 text-warning'
      : 'bg-error/20 text-error';
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${style}`}>
      {pct}%
    </span>
  );
}

function ConfidenceBar({ value, label }: { readonly value: number; readonly label: string }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'bg-success' : pct >= 50 ? 'bg-warning' : 'bg-error';
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-muted w-24">{label}</span>
      <div className="w-24 h-2 bg-border rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-[var(--font-mono)] text-text-secondary">{pct}%</span>
    </div>
  );
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function LoanPrograms() {
  const [page, setPage] = useState(1);
  const [loanType, setLoanType] = useState('');
  const [sort, setSort] = useState('program_name');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [exporting, setExporting] = useState(false);

  const queryParams = new URLSearchParams({
    page: String(page),
    limit: String(LIMIT),
    sort,
  });
  if (loanType) queryParams.set('loan_type', loanType);
  if (dateFrom) queryParams.set('date_from', dateFrom);
  if (dateTo) queryParams.set('date_to', dateTo);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['loan-programs', page, loanType, sort, dateFrom, dateTo],
    queryFn: () =>
      apiFetch<PaginatedResponse<LoanProgram>>(`/api/loan-programs?${queryParams.toString()}`),
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;

  const handleExport = async () => {
    setExporting(true);
    try {
      const exportParams = new URLSearchParams();
      if (loanType) exportParams.set('loan_type', loanType);
      if (dateFrom) exportParams.set('date_from', dateFrom);
      if (dateTo) exportParams.set('date_to', dateTo);

      const resp = await fetch(`${API_URL}/api/loan-programs/export?${exportParams.toString()}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        alert(err.error || 'Export failed');
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `loan-programs-${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text-heading">Loan Programs</h2>
        <button
          className="px-4 py-2 text-sm font-medium bg-running/15 text-running-dim rounded-lg hover:bg-running/25 disabled:opacity-50 transition-colors"
          onClick={handleExport}
          disabled={exporting}
        >
          {exporting ? 'Exporting...' : 'Export Excel'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <select
          className="border border-border rounded-lg px-3 py-2 text-sm bg-bg-card text-text-body"
          value={loanType}
          onChange={(e) => { setLoanType(e.target.value); setPage(1); }}
        >
          <option value="">All Loan Types</option>
          {LOAN_TYPES.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>

        <select
          className="border border-border rounded-lg px-3 py-2 text-sm bg-bg-card text-text-body"
          value={sort}
          onChange={(e) => { setSort(e.target.value); setPage(1); }}
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">From</label>
          <input
            type="date"
            className="border border-border rounded-lg px-3 py-2 text-sm bg-bg-card text-text-body"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted">To</label>
          <input
            type="date"
            className="border border-border rounded-lg px-3 py-2 text-sm bg-bg-card text-text-body"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          />
        </div>
      </div>

      {isLoading && <p className="text-text-muted">Loading loan programs...</p>}
      {isError && <p className="text-error">Error: {(error as Error).message}</p>}

      {data && (
        <>
          <div className="bg-bg-card rounded-lg border border-border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Program</th>
                  <th className="w-28 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bank</th>
                  <th className="w-28 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Type</th>
                  <th className="w-32 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Interest Rate</th>
                  <th className="w-24 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.data.map((program) => {
                  const isExpanded = expandedId === program.id;
                  return (
                    <Fragment key={program.id}>
                      <tr
                        className="hover:bg-bg-hover cursor-pointer transition-colors"
                        onClick={() => setExpandedId(isExpanded ? null : program.id)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] text-text-dim transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▶</span>
                            <span className="text-sm font-medium text-text-heading">{program.program_name}</span>
                          </div>
                        </td>
                        <td className="w-28 px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">{program.bank_code}</td>
                        <td className="w-28 px-4 py-3">
                          <span className="px-2 py-0.5 bg-running/15 text-running-dim rounded text-xs font-medium">
                            {program.loan_type}
                          </span>
                        </td>
                        <td className="w-32 px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">
                          {formatRange(program.min_interest_rate, program.max_interest_rate, '%')}
                        </td>
                        <td className="w-24 px-4 py-3">
                          <ConfidencePill value={program.data_confidence} />
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="bg-bg-hover/50">
                          <td colSpan={5} className="px-12 py-4">
                            <div className="space-y-3">
                              <div className="flex gap-8 text-sm">
                                <div>
                                  <span className="text-text-muted">Amount Range: </span>
                                  <span className="font-[var(--font-mono)] text-text-secondary">
                                    {formatAmountRange(program.min_amount, program.max_amount)}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-text-muted">Tenure: </span>
                                  <span className="font-[var(--font-mono)] text-text-secondary">
                                    {formatRange(program.min_tenure_months, program.max_tenure_months, ' mo')}
                                  </span>
                                </div>
                              </div>
                              <div className="flex gap-6">
                                <ConfidenceBar value={program.data_confidence} label="Confidence" />
                                <ConfidenceBar value={program.completeness_score} label="Completeness" />
                              </div>
                              {program.raw_data && (
                                <details className="mt-2">
                                  <summary className="text-xs text-text-dim cursor-pointer hover:text-text-muted">
                                    Raw data
                                  </summary>
                                  <pre className="text-xs text-text-secondary font-[var(--font-mono)] overflow-auto max-h-64 p-3 mt-2 bg-bg-card rounded border border-border">
                                    {JSON.stringify(program.raw_data, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
                {data.data.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-text-muted">
                      No loan programs found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-text-secondary">
              Showing {(page - 1) * LIMIT + 1}-{Math.min(page * LIMIT, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 text-sm border border-border rounded disabled:opacity-50 hover:bg-bg-hover text-text-body"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm text-text-secondary">
                Page {page} of {totalPages}
              </span>
              <button
                className="px-3 py-1 text-sm border border-border rounded disabled:opacity-50 hover:bg-bg-hover text-text-body"
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

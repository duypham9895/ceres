import { Fragment, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, apiPost, API_URL } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import type { CompareResponse } from '../types/dashboard';
import { formatRange, formatAmountRange } from '../utils/format';
import { useFilterState } from '../hooks/useFilterState';
import { LOAN_PROGRAM_FILTERS } from '../config/filters';
import FilterBar from '../components/filters/FilterBar';
import SummaryStrip from '../components/SummaryStrip';

interface LoanProgram {
  readonly id: string;
  readonly program_name: string;
  readonly bank_code: string;
  readonly loan_type: string;
  readonly min_interest_rate: number | null;
  readonly max_interest_rate: number | null;
  readonly min_amount: number | null;
  readonly max_amount: number | null;
  readonly min_tenor_months: number | null;
  readonly max_tenor_months: number | null;
  readonly rate_fixed: number | null;
  readonly rate_floating: number | null;
  readonly rate_promo: number | null;
  readonly rate_promo_duration_months: number | null;
  readonly data_confidence: number;
  readonly completeness_score: number;
  readonly source_url: string | null;
  readonly raw_data: Record<string, unknown> | null;
}

const LIMIT = 20;

const EXPECTED_FIELDS = [
  'program_name',
  'loan_type',
  'min_interest_rate',
  'max_interest_rate',
  'min_amount',
  'max_amount',
  'min_tenor_months',
  'max_tenor_months',
] as const;

const LOAN_TYPES = ['KPR', 'KKB', 'KTA', 'KMG'] as const;

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

function RateChips({ program }: { readonly program: LoanProgram }) {
  const hasAny = program.rate_fixed != null || program.rate_floating != null || program.rate_promo != null;
  if (!hasAny) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {program.rate_fixed != null && (
        <span className="px-1.5 py-0.5 rounded text-[9px] bg-success/10 text-success">
          Fixed {program.rate_fixed}%
        </span>
      )}
      {program.rate_floating != null && (
        <span className="px-1.5 py-0.5 rounded text-[9px] bg-running/10 text-running">
          Float {program.rate_floating}%
        </span>
      )}
      {program.rate_promo != null && (
        <span className="px-1.5 py-0.5 rounded text-[9px] bg-warning/10 text-warning">
          Promo {program.rate_promo}%{program.rate_promo_duration_months ? ` (${program.rate_promo_duration_months}mo)` : ''}
        </span>
      )}
    </div>
  );
}

export default function LoanPrograms() {
  const {
    filters, setFilter, setFilters, clearAll, clearFilter,
    toQueryString, activeCount, page, setPage,
  } = useFilterState(LOAN_PROGRAM_FILTERS);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [viewMode, setViewMode] = useState<'list' | 'compare'>('list');
  const [compareType, setCompareType] = useState<string>('KPR');

  const queryString = toQueryString();
  const paginatedQuery = queryString
    ? `${queryString}&page=${page}&limit=${LIMIT}`
    : `page=${page}&limit=${LIMIT}`;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['loan-programs', queryString, page],
    queryFn: () =>
      apiFetch<PaginatedResponse<LoanProgram>>(`/api/loan-programs?${paginatedQuery}`),
  });

  const { data: compareData } = useQuery({
    queryKey: ['loan-compare', compareType],
    queryFn: () => apiFetch<CompareResponse>(`/api/loan-programs/compare?loan_type=${compareType}`),
    enabled: viewMode === 'compare',
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;

  // Compute summary stats from current page data
  const summaryItems = data ? (() => {
    const programs = data.data;
    const loanTypeSet = new Set(programs.map((p) => p.loan_type));
    const avgCompleteness = programs.length > 0
      ? Math.round(programs.reduce((sum, p) => sum + p.completeness_score, 0) / programs.length * 100)
      : 0;
    const lowQuality = programs.filter((p) => p.completeness_score < 0.5).length;
    return [
      { label: 'programs', value: data.total, color: 'blue' as const },
      { label: 'loan types', value: loanTypeSet.size, color: 'green' as const },
      { label: '% avg completeness', value: avgCompleteness, color: avgCompleteness >= 70 ? 'green' as const : avgCompleteness >= 50 ? 'yellow' as const : 'red' as const },
      { label: 'low quality', value: lowQuality, color: lowQuality > 0 ? 'red' as const : 'gray' as const },
    ];
  })() : [];

  const handleExport = async () => {
    setExporting(true);
    try {
      const exportQuery = toQueryString();
      const resp = await fetch(
        `${API_URL}/api/loan-programs/export${exportQuery ? `?${exportQuery}` : ''}`,
      );
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

  // Compare view sorted by min rate ascending; lowest gets success bg, highest gets error bg
  const sortedCompare = compareData
    ? [...compareData.programs].sort((a, b) => {
        const aRate = a.min_interest_rate ?? Infinity;
        const bRate = b.min_interest_rate ?? Infinity;
        return aRate - bRate;
      })
    : [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text-heading">Loan Programs</h2>
        <div className="flex items-center gap-3">
          {/* View mode toggle */}
          <div className="flex gap-1 p-1 bg-bg-card border border-border rounded-lg text-xs font-medium">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 rounded transition-colors ${viewMode === 'list' ? 'bg-accent/10 text-accent' : 'text-text-dim hover:text-text-secondary'}`}
            >
              List
            </button>
            <button
              onClick={() => setViewMode('compare')}
              className={`px-3 py-1 rounded transition-colors ${viewMode === 'compare' ? 'bg-accent/10 text-accent' : 'text-text-dim hover:text-text-secondary'}`}
            >
              Compare
            </button>
          </div>
          <button
            className="px-4 py-2 text-sm font-medium bg-running/15 text-running-dim rounded-lg hover:bg-running/25 disabled:opacity-50 transition-colors"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? 'Exporting...' : 'Export Excel'}
          </button>
        </div>
      </div>

      {/* Summary strip */}
      {data && summaryItems.length > 0 && (
        <SummaryStrip items={summaryItems} />
      )}

      {/* Compare view */}
      {viewMode === 'compare' && (
        <div className="space-y-4">
          {/* Loan type selector */}
          <div className="flex gap-2">
            {LOAN_TYPES.map((type) => (
              <button
                key={type}
                onClick={() => setCompareType(type)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
                  compareType === type
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-border text-text-dim hover:text-text-secondary hover:bg-bg-hover'
                }`}
              >
                {type}
              </button>
            ))}
          </div>

          <div className="bg-bg-card rounded-lg border border-border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Bank</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Min Rate</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Max Rate</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Fixed</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Floating</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Promo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Completeness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedCompare.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-text-muted">
                      No {compareType} programs found. Try a different loan type.
                    </td>
                  </tr>
                ) : (
                  sortedCompare.map((prog, idx) => {
                    const rowBg = idx === 0 ? 'bg-success/5' : idx === sortedCompare.length - 1 ? 'bg-error/5' : '';
                    return (
                      <tr key={prog.bank_code} className={rowBg}>
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-text-heading">{prog.bank_code}</div>
                          <div className="text-[11px] text-text-muted">{prog.bank_name}</div>
                        </td>
                        <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">
                          {prog.min_interest_rate != null ? `${prog.min_interest_rate}%` : '—'}
                        </td>
                        <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">
                          {prog.max_interest_rate != null ? `${prog.max_interest_rate}%` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {prog.rate_fixed != null ? (
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-success/10 text-success">
                              {prog.rate_fixed}%
                            </span>
                          ) : <span className="text-text-dim">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          {prog.rate_floating != null ? (
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-running/10 text-running">
                              {prog.rate_floating}%
                            </span>
                          ) : <span className="text-text-dim">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          {prog.rate_promo != null ? (
                            <span className="px-1.5 py-0.5 rounded text-[9px] bg-warning/10 text-warning">
                              {prog.rate_promo}%{prog.rate_promo_duration_months ? ` (${prog.rate_promo_duration_months}mo)` : ''}
                            </span>
                          ) : <span className="text-text-dim">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <ConfidencePill value={prog.completeness_score} />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* List view */}
      {viewMode === 'list' && (
        <>
          <FilterBar
            config={LOAN_PROGRAM_FILTERS}
            filters={filters}
            onFilterChange={setFilter}
            onFilterChangeBatch={setFilters}
            onClearAll={clearAll}
            onClearFilter={clearFilter}
            activeCount={activeCount}
            pageKey="loan-programs"
            totalResults={data?.total}
          />

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
                      <th className="w-44 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Rates</th>
                      <th className="w-24 px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.data.map((program) => {
                      const isExpanded = expandedId === program.id;
                      const missingFields = EXPECTED_FIELDS.filter(
                        (f) => (program as unknown as Record<string, unknown>)[f] == null,
                      );
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
                            <td className="w-44 px-4 py-3">
                              <div className="text-sm font-[var(--font-mono)] text-text-secondary">
                                {formatRange(program.min_interest_rate, program.max_interest_rate, '%')}
                              </div>
                              <RateChips program={program} />
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
                                      <span className="text-text-muted">Tenor: </span>
                                      <span className="font-[var(--font-mono)] text-text-secondary">
                                        {formatRange(program.min_tenor_months, program.max_tenor_months, ' mo')}
                                      </span>
                                    </div>
                                  </div>
                                  {/* Missing fields tooltip */}
                                  {missingFields.length > 0 && (
                                    <p className="text-[10px] text-warning mt-1">
                                      Missing: {missingFields.join(', ')}
                                    </p>
                                  )}
                                  {program.source_url && (
                                    <div className="text-sm">
                                      <span className="text-text-muted">Source: </span>
                                      <a
                                        href={program.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-running hover:text-running-dim underline underline-offset-2"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        {program.source_url}
                                      </a>
                                    </div>
                                  )}
                                  <div className="flex items-center gap-6">
                                    <ConfidenceBar value={program.data_confidence} label="Confidence" />
                                    <ConfidenceBar value={program.completeness_score} label="Completeness" />
                                    {/* Re-parse CTA */}
                                    {program.completeness_score < 0.5 && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          apiPost(`/api/crawl/parser?bank=${program.bank_code}`)
                                            .then(() => toast.success('Re-parse triggered'))
                                            .catch(() => toast.error('Failed to trigger re-parse'));
                                        }}
                                        className="text-[10px] font-medium text-accent hover:text-accent/80 transition-colors"
                                      >
                                        Re-parse
                                      </button>
                                    )}
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
                  {data.total === 0
                    ? 'No results'
                    : `Showing ${(page - 1) * LIMIT + 1}-${Math.min(page * LIMIT, data.total)} of ${data.total}`}
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
        </>
      )}
    </div>
  );
}

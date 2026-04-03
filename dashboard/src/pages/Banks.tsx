import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiFetch, apiPost } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import CrawlButton from '../components/CrawlButton';
import SummaryStrip from '../components/SummaryStrip';
import CompletenessBar from '../components/CompletenessBar';
import { formatDate } from '../utils/format';
import { useFilterState } from '../hooks/useFilterState';
import { BANK_FILTERS } from '../config/filters';
import FilterBar from '../components/filters/FilterBar';

interface Bank {
  id: string;
  bank_code: string;
  bank_name: string;
  bank_category: string;
  website_status: string;
  last_crawled_at: string | null;
  programs_count: number;
  crawl_streak?: number;
  success_rate_30d?: number;
  avg_quality?: number;
}

type SortDir = 'asc' | 'desc';

const LIMIT = 20;

const SORTABLE_COLUMNS: { key: string; label: string }[] = [
  { key: 'bank_code', label: 'Code' },
  { key: 'bank_name', label: 'Name' },
  { key: 'bank_category', label: 'Category' },
  { key: 'website_status', label: 'Status' },
  { key: 'last_crawled_at', label: 'Last Crawled' },
  { key: 'programs_count', label: 'Programs' },
  { key: 'crawl_streak', label: 'Crawl Health' },
  { key: 'avg_quality', label: 'Data Quality' },
];

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-text-dim opacity-40">↕</span>;
  return <span className="ml-1 text-accent">{dir === 'asc' ? '↑' : '↓'}</span>;
}

export default function Banks() {
  const {
    filters, setFilter, setFilters, clearAll, clearFilter,
    toQueryString, activeCount, page, setPage,
  } = useFilterState(BANK_FILTERS);
  const navigate = useNavigate();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<string>('bank_name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const queryString = toQueryString();
  const paginatedQuery = queryString
    ? `${queryString}&page=${page}&limit=${LIMIT}`
    : `page=${page}&limit=${LIMIT}`;

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['banks', queryString, page],
    queryFn: () => apiFetch<PaginatedResponse<Bank>>(`/api/banks?${paginatedQuery}`),
  });

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0;

  const sortedBanks = useMemo(() => {
    if (!data?.data) return [];
    return [...data.data].sort((a, b) => {
      const aVal = a[sortBy as keyof Bank] ?? '';
      const bVal = b[sortBy as keyof Bank] ?? '';
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [data?.data, sortBy, sortDir]);

  const activeCount_ = data?.data.filter(b => b.website_status === 'active').length ?? 0;
  const unreachableCount = data?.data.filter(b => b.website_status === 'unreachable').length ?? 0;
  const blockedCount = data?.data.filter(b => b.website_status === 'blocked').length ?? 0;

  const allSelected = sortedBanks.length > 0 && sortedBanks.every(b => selected.has(b.id));

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(sortedBanks.map(b => b.id)));
    }
  };

  const toggleBank = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('asc');
    }
  };

  const bulkCrawl = async () => {
    const bankIds = Array.from(selected);
    await Promise.all(bankIds.map(id => {
      const bank = data?.data.find(b => b.id === id);
      return bank ? apiPost(`/api/crawl/crawler?bank=${bank.bank_code}`) : Promise.resolve();
    }));
    toast.success(`Crawl triggered for ${bankIds.length} banks`);
    setSelected(new Set());
  };

  const bulkRelearn = async () => {
    const bankIds = Array.from(selected);
    await Promise.all(bankIds.map(id => {
      const bank = data?.data.find(b => b.id === id);
      return bank ? apiPost(`/api/crawl/learning?bank=${bank.bank_code}`) : Promise.resolve();
    }));
    toast.success(`Re-learn triggered for ${bankIds.length} banks`);
    setSelected(new Set());
  };

  const colLabel = (key: string) => SORTABLE_COLUMNS.find(c => c.key === key)?.label ?? key;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-text-heading">Banks</h2>
      </div>

      {data && (
        <SummaryStrip items={[
          { label: 'active', value: activeCount_, color: 'green' },
          { label: 'unreachable', value: unreachableCount, color: 'yellow' },
          { label: 'blocked', value: blockedCount, color: 'red' },
        ]} />
      )}

      <FilterBar
        config={BANK_FILTERS}
        filters={filters}
        onFilterChange={setFilter}
        onFilterChangeBatch={setFilters}
        onClearAll={clearAll}
        onClearFilter={clearFilter}
        activeCount={activeCount}
        pageKey="banks"
        totalResults={data?.total}
      />

      {isLoading && <p className="text-text-muted">Loading banks...</p>}
      {isError && <p className="text-error">Error: {error instanceof Error ? error.message : 'Failed to load banks'}</p>}

      {data && (
        <>
          {selected.size > 0 && (
            <div className="flex items-center gap-3 px-4 py-2 bg-accent/5 border border-accent/20 rounded-lg mb-3">
              <span className="text-xs text-text-dim">{selected.size} selected</span>
              <button onClick={bulkCrawl} className="text-xs font-medium text-accent hover:text-accent/80">
                Crawl Selected
              </button>
              <button onClick={bulkRelearn} className="text-xs font-medium text-accent hover:text-accent/80">
                Re-learn Selected
              </button>
              <button onClick={() => setSelected(new Set())} className="text-xs text-text-dim hover:text-text-muted ml-auto">
                Clear
              </button>
            </div>
          )}

          <div className="overflow-x-auto bg-bg-card rounded-lg shadow">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-bg-card">
                <tr>
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      className="rounded border-border"
                    />
                  </th>
                  {SORTABLE_COLUMNS.map(col => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase cursor-pointer select-none hover:text-text-body"
                    >
                      {colLabel(col.key)}
                      <SortIcon active={sortBy === col.key} dir={sortDir} />
                    </th>
                  ))}
                  <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {sortedBanks.map((bank) => (
                  <tr
                    key={bank.id}
                    onClick={() => navigate(`/banks/${bank.id}`)}
                    className="hover:bg-bg-hover cursor-pointer"
                  >
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selected.has(bank.id)}
                        onChange={() => toggleBank(bank.id)}
                        className="rounded border-border"
                      />
                    </td>
                    <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-heading">{bank.bank_code}</td>
                    <td className="px-4 py-3 text-sm text-text-heading">{bank.bank_name}</td>
                    <td className="px-4 py-3 text-sm text-text-secondary">{bank.bank_category}</td>
                    <td className="px-4 py-3 text-sm"><StatusBadge status={bank.website_status} /></td>
                    <td className="px-4 py-3 text-sm text-text-secondary">{formatDate(bank.last_crawled_at)}</td>
                    <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-heading">{bank.programs_count}</td>
                    <td className="px-4 py-3 text-sm text-text-secondary whitespace-nowrap">
                      {bank.crawl_streak != null || bank.success_rate_30d != null
                        ? `🔥${bank.crawl_streak ?? 0} · ${Math.round((bank.success_rate_30d ?? 0) * 100)}%`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <CompletenessBar score={bank.avg_quality ?? 0} />
                    </td>
                    <td className="px-4 py-3 text-sm" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-2">
                        <CrawlButton agent="daily" label="Crawl" bank={bank.bank_code} variant="secondary" />
                        <button
                          onClick={() => apiPost(`/api/crawl/learning?bank=${bank.bank_code}`).then(() => toast.success(`Re-learn triggered for ${bank.bank_name}`)).catch(() => toast.error('Failed to trigger re-learn'))}
                          className="px-4 py-2 rounded-md font-medium text-[12px] transition-colors bg-bg-hover text-text-secondary border border-border-light hover:text-text-body"
                        >
                          Re-learn
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-text-secondary">
              Showing {(page - 1) * LIMIT + 1}–{Math.min(page * LIMIT, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 text-sm border border-border rounded-md disabled:opacity-50 hover:bg-bg-hover text-text-body"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border border-border rounded-md disabled:opacity-50 hover:bg-bg-hover text-text-body"
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

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../api/client';
import type { PaginatedResponse } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import CrawlButton from '../components/CrawlButton';

interface Bank {
  id: number;
  bank_code: string;
  bank_name: string;
  bank_category: string;
  website_status: string;
  last_crawled_at: string | null;
  programs_count: number;
}

const CATEGORIES = ['All', 'BUMN', 'SWASTA_NASIONAL', 'BPD', 'ASING', 'SYARIAH'] as const;
const LIMIT = 20;

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

export default function Banks() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<string>('All');
  const navigate = useNavigate();

  const queryParams = new URLSearchParams({
    page: String(page),
    limit: String(LIMIT),
  });
  if (category !== 'All') {
    queryParams.set('category', category);
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['banks', page, category],
    queryFn: () => apiFetch<PaginatedResponse<Bank>>(`/api/banks?${queryParams.toString()}`),
  });

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Banks</h2>
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-600">
            Category:
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="ml-2 border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {isLoading && <p className="text-gray-500">Loading banks...</p>}
      {isError && <p className="text-red-500">Error: {error instanceof Error ? error.message : 'Failed to load banks'}</p>}

      {data && (
        <>
          <div className="overflow-x-auto bg-white rounded-lg shadow">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Crawled</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Programs</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.data.map((bank) => (
                  <tr
                    key={bank.id}
                    onClick={() => navigate(`/banks/${bank.id}`)}
                    className="hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-4 py-3 text-sm font-mono text-gray-900">{bank.bank_code}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{bank.bank_name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{bank.bank_category}</td>
                    <td className="px-4 py-3 text-sm"><StatusBadge status={bank.website_status} /></td>
                    <td className="px-4 py-3 text-sm text-gray-600">{formatDate(bank.last_crawled_at)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{bank.programs_count}</td>
                    <td className="px-4 py-3 text-sm" onClick={(e) => e.stopPropagation()}>
                      <CrawlButton agent="daily" label="Crawl" bank={bank.bank_code} variant="secondary" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-600">
              Showing {(page - 1) * LIMIT + 1}–{Math.min(page * LIMIT, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
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

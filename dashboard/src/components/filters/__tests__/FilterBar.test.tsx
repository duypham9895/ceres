import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import FilterBar from '../FilterBar';
import type { FilterConfig, FilterValues } from '../types';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function Wrapper({ children }: { readonly children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const CONFIGS: readonly FilterConfig[] = [
  {
    key: 'status',
    label: 'Status',
    type: 'multi-select',
    options: [
      { value: 'success', label: 'Success' },
      { value: 'failed', label: 'Failed' },
    ],
  },
  {
    key: 'date',
    label: 'Date',
    type: 'date-range',
    urlKeys: { from: 'date_from', to: 'date_to' },
    presets: ['today', 'last_7_days'],
  },
  {
    key: 'sort',
    label: 'Sort',
    type: 'select',
    excludeFromClearAll: true,
    options: [
      { value: 'name', label: 'Name' },
      { value: 'date', label: 'Date' },
    ],
  },
];

const defaultFilters: FilterValues = {
  status: ['success', 'failed'],
  date_from: '2026-01-01',
  date_to: '2026-01-31',
  sort: 'name',
};

const emptyFilters: FilterValues = {
  status: [],
  date_from: null,
  date_to: null,
  sort: null,
};

describe('FilterBar', () => {
  it('renders active filter chips', () => {
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={vi.fn()}
          onClearFilter={vi.fn()}
          activeCount={2}
          pageKey="test"
        />
      </Wrapper>,
    );

    expect(screen.getByText('Status:')).toBeTruthy();
    expect(screen.getByText('2 selected')).toBeTruthy();
    expect(screen.getByText('Date:')).toBeTruthy();
  });

  it('renders "Add filter" button when inactive filters exist', () => {
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={emptyFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={vi.fn()}
          onClearFilter={vi.fn()}
          activeCount={0}
          pageKey="test"
        />
      </Wrapper>,
    );

    expect(screen.getByText('+ Add filter')).toBeTruthy();
  });

  it('shows "Clear all" with count when filters active', () => {
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={vi.fn()}
          onClearFilter={vi.fn()}
          activeCount={2}
          pageKey="test"
        />
      </Wrapper>,
    );

    expect(screen.getByText('Clear all (2)')).toBeTruthy();
  });

  it('calls onClearAll when "Clear all" clicked', () => {
    const onClearAll = vi.fn();
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={onClearAll}
          onClearFilter={vi.fn()}
          activeCount={2}
          pageKey="test"
        />
      </Wrapper>,
    );

    fireEvent.click(screen.getByText('Clear all (2)'));
    expect(onClearAll).toHaveBeenCalledOnce();
  });

  it('shows Presets button', () => {
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={emptyFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={vi.fn()}
          onClearFilter={vi.fn()}
          activeCount={0}
          pageKey="test"
        />
      </Wrapper>,
    );

    expect(screen.getByText('Presets')).toBeTruthy();
  });

  it('shows total results when provided', () => {
    render(
      <Wrapper>
        <FilterBar
          config={CONFIGS}
          filters={defaultFilters}
          onFilterChange={vi.fn()}
          onFilterChangeBatch={vi.fn()}
          onClearAll={vi.fn()}
          onClearFilter={vi.fn()}
          activeCount={2}
          pageKey="test"
          totalResults={42}
        />
      </Wrapper>,
    );

    expect(screen.getByText('42')).toBeTruthy();
  });
});

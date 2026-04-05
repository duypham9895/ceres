import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useFilterState } from '../useFilterState';
import type { FilterConfig } from '../../components/filters/types';

// Mock react-router-dom useSearchParams
const mockSearchParams = new URLSearchParams();
const mockSetSearchParams = vi.fn((updater: (prev: URLSearchParams) => URLSearchParams) => {
  const next = updater(mockSearchParams);
  // Simulate the URL update
  for (const [key] of [...mockSearchParams.entries()]) {
    mockSearchParams.delete(key);
  }
  for (const [key, value] of next.entries()) {
    mockSearchParams.set(key, value);
  }
});

vi.mock('react-router-dom', () => ({
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
}));

const TEST_CONFIGS: readonly FilterConfig[] = [
  {
    key: 'loan_type',
    label: 'Loan Type',
    type: 'multi-select',
    options: [
      { value: 'KPR', label: 'KPR' },
      { value: 'KPA', label: 'KPA' },
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
    key: 'rate',
    label: 'Rate',
    type: 'range',
    urlKeys: { min: 'rate_min', max: 'rate_max' },
    min: 0,
    max: 30,
    step: 0.5,
    suffix: '%',
  },
  {
    key: 'sort',
    label: 'Sort',
    type: 'select',
    excludeFromClearAll: true,
    options: [
      { value: 'name', label: 'Name' },
      { value: 'rate', label: 'Rate' },
    ],
  },
];

beforeEach(() => {
  for (const [key] of [...mockSearchParams.entries()]) {
    mockSearchParams.delete(key);
  }
  mockSetSearchParams.mockClear();
});

describe('useFilterState', () => {
  it('parses empty URL params to defaults', () => {
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    expect(result.current.filters.loan_type).toEqual([]);
    expect(result.current.filters.date_from).toBeNull();
    expect(result.current.filters.date_to).toBeNull();
    expect(result.current.filters.rate_min).toBeNull();
    expect(result.current.filters.rate_max).toBeNull();
    expect(result.current.filters.sort).toBeNull();
    expect(result.current.activeCount).toBe(0);
    expect(result.current.page).toBe(1);
  });

  it('parses multi-select from URL', () => {
    mockSearchParams.set('loan_type', 'KPR,KPA');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    expect(result.current.filters.loan_type).toEqual(['KPR', 'KPA']);
  });

  it('parses date-range from URL', () => {
    mockSearchParams.set('date_from', '2026-01-01');
    mockSearchParams.set('date_to', '2026-01-31');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    expect(result.current.filters.date_from).toBe('2026-01-01');
    expect(result.current.filters.date_to).toBe('2026-01-31');
  });

  it('parses range values and drops invalid ones', () => {
    mockSearchParams.set('rate_min', '5');
    mockSearchParams.set('rate_max', 'abc');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    expect(result.current.filters.rate_min).toBe(5);
    expect(result.current.filters.rate_max).toBeNull(); // invalid → dropped
  });

  it('setFilter updates URL and resets page', () => {
    mockSearchParams.set('page', '3');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    act(() => {
      result.current.setFilter('loan_type', ['KPR']);
    });

    expect(mockSetSearchParams).toHaveBeenCalled();
    // The updater should delete 'page' (reset to 1)
    const updater = mockSetSearchParams.mock.calls[0][0];
    const prev = new URLSearchParams('page=3');
    const next = updater(prev);
    expect(next.get('loan_type')).toBe('KPR');
    expect(next.has('page')).toBe(false);
  });

  it('clearAll resets filters but NOT sort (excludeFromClearAll)', () => {
    mockSearchParams.set('loan_type', 'KPR');
    mockSearchParams.set('sort', 'rate');
    mockSearchParams.set('date_from', '2026-01-01');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    act(() => {
      result.current.clearAll();
    });

    const updater = mockSetSearchParams.mock.calls[0][0];
    const prev = new URLSearchParams('loan_type=KPR&sort=rate&date_from=2026-01-01');
    const next = updater(prev);

    // loan_type and date_from should be cleared
    expect(next.has('loan_type')).toBe(false);
    expect(next.has('date_from')).toBe(false);
    // sort should be preserved (excludeFromClearAll)
    expect(next.get('sort')).toBe('rate');
  });

  it('toQueryString serializes active filters', () => {
    mockSearchParams.set('loan_type', 'KPR,KPA');
    mockSearchParams.set('rate_min', '5');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    const qs = result.current.toQueryString();
    const parsed = new URLSearchParams(qs);
    expect(parsed.get('loan_type')).toBe('KPR,KPA');
    expect(parsed.get('rate_min')).toBe('5');
    expect(parsed.has('date_from')).toBe(false);
  });

  it('activeCount excludes sort (excludeFromClearAll)', () => {
    mockSearchParams.set('loan_type', 'KPR');
    mockSearchParams.set('sort', 'rate');
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    // loan_type is active, sort is excluded from count
    expect(result.current.activeCount).toBe(1);
  });

  it('setFilters batch-updates multiple params', () => {
    const { result } = renderHook(() => useFilterState(TEST_CONFIGS));

    act(() => {
      result.current.setFilters({
        date_from: '2026-01-01',
        date_to: '2026-01-31',
      });
    });

    const updater = mockSetSearchParams.mock.calls[0][0];
    const next = updater(new URLSearchParams());
    expect(next.get('date_from')).toBe('2026-01-01');
    expect(next.get('date_to')).toBe('2026-01-31');
  });
});

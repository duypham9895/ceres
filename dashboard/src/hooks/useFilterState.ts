import { useCallback, useMemo, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { FilterConfig, FilterValues } from '../components/filters/types';

/** Get all URL param keys that a filter config owns. */
function getUrlKeys(config: FilterConfig): string[] {
  switch (config.type) {
    case 'multi-select':
      return [config.key];
    case 'date-range':
      return [config.urlKeys.from, config.urlKeys.to];
    case 'range':
      return [config.urlKeys.min, config.urlKeys.max];
    case 'select':
      return [config.key];
  }
}

/** Parse URL search params into FilterValues based on config. */
function parseFilters(
  params: URLSearchParams,
  configs: readonly FilterConfig[],
): FilterValues {
  const values: FilterValues = {};
  for (const config of configs) {
    switch (config.type) {
      case 'multi-select': {
        const raw = params.get(config.key);
        values[config.key] = raw
          ? raw.split(',').map((v) => v.trim()).filter(Boolean)
          : [];
        break;
      }
      case 'date-range': {
        values[config.urlKeys.from] = params.get(config.urlKeys.from) ?? null;
        values[config.urlKeys.to] = params.get(config.urlKeys.to) ?? null;
        break;
      }
      case 'range': {
        const minRaw = params.get(config.urlKeys.min);
        const maxRaw = params.get(config.urlKeys.max);
        const minVal = minRaw !== null ? parseFloat(minRaw) : null;
        const maxVal = maxRaw !== null ? parseFloat(maxRaw) : null;
        values[config.urlKeys.min] = Number.isFinite(minVal) ? minVal : null;
        values[config.urlKeys.max] = Number.isFinite(maxVal) ? maxVal : null;
        break;
      }
      case 'select': {
        values[config.key] = params.get(config.key) ?? null;
        break;
      }
    }
  }
  return values;
}

/** Serialize FilterValues back to URLSearchParams string for API calls. */
function serializeForApi(
  values: FilterValues,
  configs: readonly FilterConfig[],
): string {
  const params = new URLSearchParams();
  for (const config of configs) {
    switch (config.type) {
      case 'multi-select': {
        const arr = values[config.key];
        if (Array.isArray(arr) && arr.length > 0) {
          params.set(config.key, arr.join(','));
        }
        break;
      }
      case 'date-range': {
        const from = values[config.urlKeys.from];
        const to = values[config.urlKeys.to];
        if (typeof from === 'string' && from) params.set(config.urlKeys.from, from);
        if (typeof to === 'string' && to) params.set(config.urlKeys.to, to);
        break;
      }
      case 'range': {
        const min = values[config.urlKeys.min];
        const max = values[config.urlKeys.max];
        if (min !== null && min !== undefined) params.set(config.urlKeys.min, String(min));
        if (max !== null && max !== undefined) params.set(config.urlKeys.max, String(max));
        break;
      }
      case 'select': {
        const val = values[config.key];
        if (typeof val === 'string' && val) params.set(config.key, val);
        break;
      }
    }
  }
  return params.toString();
}

/** Check if a filter has a non-default (active) value. */
function isActive(config: FilterConfig, values: FilterValues): boolean {
  switch (config.type) {
    case 'multi-select': {
      const arr = values[config.key];
      return Array.isArray(arr) && arr.length > 0;
    }
    case 'date-range': {
      return values[config.urlKeys.from] !== null || values[config.urlKeys.to] !== null;
    }
    case 'range': {
      return values[config.urlKeys.min] !== null || values[config.urlKeys.max] !== null;
    }
    case 'select': {
      return values[config.key] !== null;
    }
  }
}

export interface UseFilterStateReturn {
  readonly filters: FilterValues;
  readonly setFilter: (key: string, value: unknown) => void;
  readonly setFilters: (updates: FilterValues) => void;
  readonly clearAll: () => void;
  readonly clearFilter: (config: FilterConfig) => void;
  readonly toQueryString: () => string;
  readonly activeCount: number;
  readonly page: number;
  readonly setPage: (p: number) => void;
}

export function useFilterState(
  configs: readonly FilterConfig[],
): UseFilterStateReturn {
  const [searchParams, setSearchParams] = useSearchParams();
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Cleanup debounce timers on unmount
  useEffect(() => {
    const timers = debounceTimers.current;
    return () => {
      for (const t of Object.values(timers)) clearTimeout(t);
    };
  }, []);

  const filters = useMemo(
    () => parseFilters(searchParams, configs),
    [searchParams, configs],
  );

  const page = useMemo(() => {
    const p = parseInt(searchParams.get('page') ?? '1', 10);
    return Number.isFinite(p) && p >= 1 ? p : 1;
  }, [searchParams]);

  const setPage = useCallback(
    (p: number) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (p <= 1) {
          next.delete('page');
        } else {
          next.set('page', String(p));
        }
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  /** Update a single URL param and reset page to 1. */
  const setFilter = useCallback(
    (key: string, value: unknown) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value === null || value === undefined || value === '' ||
            (Array.isArray(value) && value.length === 0)) {
          next.delete(key);
        } else if (Array.isArray(value)) {
          next.set(key, value.join(','));
        } else {
          next.set(key, String(value));
        }
        next.delete('page'); // reset pagination
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  /** Batch-update multiple URL params and reset page to 1. */
  const setFilters = useCallback(
    (updates: FilterValues) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(updates)) {
          if (value === null || value === undefined || value === '' ||
              (Array.isArray(value) && value.length === 0)) {
            next.delete(key);
          } else if (Array.isArray(value)) {
            next.set(key, value.join(','));
          } else {
            next.set(key, String(value));
          }
        }
        next.delete('page');
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  /** Clear all filters except those with excludeFromClearAll. */
  const clearAll = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const config of configs) {
        if (config.type === 'select' && config.excludeFromClearAll) continue;
        for (const k of getUrlKeys(config)) {
          next.delete(k);
        }
      }
      next.delete('page');
      return next;
    }, { replace: true });
  }, [setSearchParams, configs]);

  /** Clear a single filter. */
  const clearFilter = useCallback(
    (config: FilterConfig) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const k of getUrlKeys(config)) {
          next.delete(k);
        }
        next.delete('page');
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  const toQueryString = useCallback(
    () => serializeForApi(filters, configs),
    [filters, configs],
  );

  const activeCount = useMemo(
    () => configs.filter((c) => {
      if (c.type === 'select' && c.excludeFromClearAll) return false;
      return isActive(c, filters);
    }).length,
    [configs, filters],
  );

  return {
    filters,
    setFilter,
    setFilters,
    clearAll,
    clearFilter,
    toQueryString,
    activeCount,
    page,
    setPage,
  };
}

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as Checkbox from '@radix-ui/react-checkbox';
import { apiFetch } from '../../../api/client';
import type { MultiSelectFilterConfig, FilterOption } from '../types';

interface MultiSelectEditorProps {
  readonly config: MultiSelectFilterConfig;
  readonly value: string[];
  readonly onChange: (value: string[]) => void;
}

export default function MultiSelectEditor({
  config,
  value,
  onChange,
}: MultiSelectEditorProps) {
  const [search, setSearch] = useState('');

  const { data: dynamicOptions, isLoading, isError, refetch } = useQuery({
    queryKey: ['filter-options', config.optionsEndpoint],
    queryFn: () => apiFetch<{ data: Record<string, unknown>[] }>(
      `${config.optionsEndpoint}?limit=100`,
    ),
    enabled: !!config.optionsEndpoint,
    staleTime: 5 * 60 * 1000,
  });

  const options: FilterOption[] = useMemo(() => {
    if (config.options) return [...config.options];
    if (!dynamicOptions?.data || !config.optionLabelKey || !config.optionValueKey) return [];
    return dynamicOptions.data.map((item) => ({
      value: String(item[config.optionValueKey!]),
      label: String(item[config.optionLabelKey!]),
    }));
  }, [config, dynamicOptions]);

  const filtered = useMemo(() => {
    if (!search) return options;
    const q = search.toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, search]);

  const toggle = (optionValue: string) => {
    const next = value.includes(optionValue)
      ? value.filter((v) => v !== optionValue)
      : [...value, optionValue];
    onChange(next);
  };

  if (config.optionsEndpoint && isLoading) {
    return <div className="px-2 py-4 text-xs text-text-muted">Loading...</div>;
  }

  if (config.optionsEndpoint && isError) {
    return (
      <div className="px-2 py-4 text-xs text-error">
        Failed to load options.{' '}
        <button
          className="underline text-running-dim"
          onClick={() => refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (options.length === 0) {
    return <div className="px-2 py-4 text-xs text-text-muted">No options available</div>;
  }

  return (
    <div>
      <input
        type="text"
        placeholder="Search..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body placeholder:text-text-dim mb-1.5 outline-none focus:border-running/50"
      />
      {value.length > 0 && (
        <div className="flex justify-between px-1 mb-1">
          <button
            className="text-[11px] text-text-dim hover:text-text-muted"
            onClick={() => onChange([])}
          >
            Clear
          </button>
          <span className="text-[11px] text-text-dim">{value.length} selected</span>
        </div>
      )}
      <div className="max-h-48 overflow-y-auto">
        {filtered.map((option) => {
          const checked = value.includes(option.value);
          return (
            <label
              key={option.value}
              className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-[13px] hover:bg-bg-hover ${
                checked ? 'text-text-heading' : 'text-text-secondary'
              }`}
            >
              <Checkbox.Root
                checked={checked}
                onCheckedChange={() => toggle(option.value)}
                className="w-4 h-4 rounded border border-border bg-bg-primary flex items-center justify-center data-[state=checked]:bg-running data-[state=checked]:border-running"
              >
                <Checkbox.Indicator className="text-white text-[10px]">✓</Checkbox.Indicator>
              </Checkbox.Root>
              {option.label}
            </label>
          );
        })}
      </div>
    </div>
  );
}

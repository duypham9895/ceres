import { useState } from 'react';
import FilterPopover from './FilterPopover';
import MultiSelectEditor from './editors/MultiSelectEditor';
import DateRangeEditor from './editors/DateRangeEditor';
import RangeEditor from './editors/RangeEditor';
import SelectEditor from './editors/SelectEditor';
import type { FilterConfig, FilterValues } from './types';

interface FilterChipProps {
  readonly config: FilterConfig;
  readonly filters: FilterValues;
  readonly onFilterChange: (key: string, value: unknown) => void;
  readonly onFilterChangeBatch: (updates: FilterValues) => void;
  readonly onClear: () => void;
}

function getDisplayValue(config: FilterConfig, filters: FilterValues): string | null {
  switch (config.type) {
    case 'multi-select': {
      const arr = filters[config.key];
      if (!Array.isArray(arr) || arr.length === 0) return null;
      if (arr.length === 1) {
        const opt = config.options?.find((o) => o.value === arr[0]);
        return opt?.label ?? arr[0];
      }
      return `${arr.length} selected`;
    }
    case 'date-range': {
      const from = filters[config.urlKeys.from];
      const to = filters[config.urlKeys.to];
      if (!from && !to) return null;
      if (from && to) return `${from} – ${to}`;
      return from ? `From ${from}` : `Until ${to}`;
    }
    case 'range': {
      const min = filters[config.urlKeys.min];
      const max = filters[config.urlKeys.max];
      if (min === null && max === null) return null;
      if (min !== null && max !== null) return `${min}${config.suffix} – ${max}${config.suffix}`;
      return min !== null ? `≥ ${min}${config.suffix}` : `≤ ${max}${config.suffix}`;
    }
    case 'select': {
      const val = filters[config.key];
      if (typeof val !== 'string') return null;
      const opt = config.options.find((o) => o.value === val);
      return opt?.label ?? val;
    }
  }
}

function renderEditor(
  config: FilterConfig,
  filters: FilterValues,
  onFilterChange: (key: string, value: unknown) => void,
  onFilterChangeBatch: (updates: FilterValues) => void,
) {
  switch (config.type) {
    case 'multi-select':
      return (
        <MultiSelectEditor
          config={config}
          value={(filters[config.key] as string[]) ?? []}
          onChange={(v) => onFilterChange(config.key, v)}
        />
      );
    case 'date-range':
      return (
        <DateRangeEditor
          config={config}
          fromValue={(filters[config.urlKeys.from] as string) ?? null}
          toValue={(filters[config.urlKeys.to] as string) ?? null}
          onChange={(from, to) =>
            onFilterChangeBatch({
              [config.urlKeys.from]: from,
              [config.urlKeys.to]: to,
            })
          }
        />
      );
    case 'range':
      return (
        <RangeEditor
          config={config}
          minValue={(filters[config.urlKeys.min] as number) ?? null}
          maxValue={(filters[config.urlKeys.max] as number) ?? null}
          onChange={(min, max) =>
            onFilterChangeBatch({
              [config.urlKeys.min]: min,
              [config.urlKeys.max]: max,
            })
          }
        />
      );
    case 'select':
      return (
        <SelectEditor
          config={config}
          value={(filters[config.key] as string) ?? null}
          onChange={(v) => onFilterChange(config.key, v)}
        />
      );
  }
}

export default function FilterChip({
  config,
  filters,
  onFilterChange,
  onFilterChangeBatch,
  onClear,
}: FilterChipProps) {
  const [open, setOpen] = useState(false);
  const displayValue = getDisplayValue(config, filters);
  const isActive = displayValue !== null;

  return (
    <FilterPopover
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[13px] transition-colors ${
            isActive
              ? 'bg-running/15 border border-running/30 text-running-dim'
              : 'bg-bg-hover border border-border text-text-muted hover:text-text-body'
          }`}
        >
          <span className="text-text-muted font-medium">{config.label}:</span>
          <span>{displayValue ?? 'Any'}</span>
          {isActive && (
            <span
              role="button"
              onClick={(e) => { e.stopPropagation(); onClear(); setOpen(false); }}
              className="ml-0.5 w-4 h-4 flex items-center justify-center rounded text-[10px] text-text-dim hover:bg-error/20 hover:text-error"
            >
              ✕
            </span>
          )}
        </button>
      }
    >
      {renderEditor(config, filters, onFilterChange, onFilterChangeBatch)}
    </FilterPopover>
  );
}

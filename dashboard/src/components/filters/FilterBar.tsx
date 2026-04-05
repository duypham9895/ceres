import { useState } from 'react';
import FilterChip from './FilterChip';
import FilterPopover from './FilterPopover';
import PresetManager from './PresetManager';
import type { FilterConfig, FilterValues } from './types';

interface FilterBarProps {
  readonly config: readonly FilterConfig[];
  readonly filters: FilterValues;
  readonly onFilterChange: (key: string, value: unknown) => void;
  readonly onFilterChangeBatch: (updates: FilterValues) => void;
  readonly onClearAll: () => void;
  readonly onClearFilter: (config: FilterConfig) => void;
  readonly activeCount: number;
  readonly pageKey: string;
  readonly totalResults?: number;
  readonly totalUnfiltered?: number;
}

function isFilterActive(config: FilterConfig, filters: FilterValues): boolean {
  switch (config.type) {
    case 'multi-select': {
      const arr = filters[config.key];
      return Array.isArray(arr) && arr.length > 0;
    }
    case 'date-range':
      return filters[config.urlKeys.from] !== null || filters[config.urlKeys.to] !== null;
    case 'range':
      return filters[config.urlKeys.min] !== null || filters[config.urlKeys.max] !== null;
    case 'select':
      return filters[config.key] !== null;
  }
}

export default function FilterBar({
  config,
  filters,
  onFilterChange,
  onFilterChangeBatch,
  onClearAll,
  onClearFilter,
  activeCount,
  pageKey,
  totalResults,
  totalUnfiltered,
}: FilterBarProps) {
  const [addOpen, setAddOpen] = useState(false);

  // Filters that are currently active (shown as chips)
  const activeConfigs = config.filter((c) => isFilterActive(c, filters));
  // Filters that can still be added
  const inactiveConfigs = config.filter(
    (c) => !isFilterActive(c, filters) && !(c.type === 'select' && c.excludeFromClearAll),
  );
  // Sort filter (always shown if it exists)
  const sortConfig = config.find(
    (c) => c.type === 'select' && c.excludeFromClearAll,
  );

  return (
    <div className="bg-bg-card border border-border rounded-lg px-3 py-2.5 mb-4">
      <div className="flex items-center gap-2 flex-wrap">
        {/* Presets */}
        <PresetManager
          pageKey={pageKey}
          config={config}
          filters={filters}
          onApply={onFilterChangeBatch}
        />

        {/* Active filter chips */}
        {activeConfigs.map((c) => (
          <FilterChip
            key={c.key}
            config={c}
            filters={filters}
            onFilterChange={onFilterChange}
            onFilterChangeBatch={onFilterChangeBatch}
            onClear={() => onClearFilter(c)}
          />
        ))}

        {/* Sort chip (always visible if configured) */}
        {sortConfig && (
          <FilterChip
            config={sortConfig}
            filters={filters}
            onFilterChange={onFilterChange}
            onFilterChangeBatch={onFilterChangeBatch}
            onClear={() => onClearFilter(sortConfig)}
          />
        )}

        {/* Add filter button */}
        {inactiveConfigs.length > 0 && (
          <FilterPopover
            open={addOpen}
            onOpenChange={setAddOpen}
            trigger={
              <button className="inline-flex items-center px-2.5 py-1 rounded-md text-[13px] border border-dashed border-border text-text-dim hover:border-text-muted hover:text-text-muted transition-colors">
                + Add filter
              </button>
            }
            minWidth={180}
          >
            <div className="text-[11px] uppercase tracking-wide text-text-dim px-1 mb-1">
              Add filter
            </div>
            {inactiveConfigs.map((c) => (
              <button
                key={c.key}
                onClick={() => {
                  // Just close the popover — user will click the chip to set value
                  // We need to activate the filter with an empty/default value first
                  if (c.type === 'multi-select') {
                    // Don't set anything — user opens chip to select
                  }
                  setAddOpen(false);
                }}
                className="w-full text-left px-2 py-1.5 rounded text-[13px] text-text-secondary hover:bg-bg-hover"
              >
                {c.label}
              </button>
            ))}
          </FilterPopover>
        )}
      </div>

      {/* Meta row */}
      {(activeCount > 0 || totalResults !== undefined) && (
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-border">
          <span className="text-[12px] text-text-dim">
            {totalResults !== undefined && totalUnfiltered !== undefined
              ? <>Showing <strong className="text-text-muted">{totalResults}</strong> of {totalUnfiltered}</>
              : totalResults !== undefined
                ? <><strong className="text-text-muted">{totalResults}</strong> results</>
                : null
            }
          </span>
          <div className="flex items-center gap-3">
            {activeCount > 0 && (
              <button
                onClick={onClearAll}
                className="text-[12px] text-error/70 hover:text-error"
              >
                Clear all ({activeCount})
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

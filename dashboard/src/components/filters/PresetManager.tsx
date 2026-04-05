import { useState, useMemo, useCallback } from 'react';
import FilterPopover from './FilterPopover';
import type { FilterConfig, FilterValues, Preset } from './types';

interface PresetManagerProps {
  readonly pageKey: string;
  readonly config: readonly FilterConfig[];
  readonly filters: FilterValues;
  readonly onApply: (filters: FilterValues) => void;
}

function storageKey(pageKey: string): string {
  return `ceres-filter-presets-${pageKey}`;
}

function loadPresets(pageKey: string): Preset[] {
  try {
    const raw = localStorage.getItem(storageKey(pageKey));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function savePresets(pageKey: string, presets: Preset[]): boolean {
  try {
    localStorage.setItem(storageKey(pageKey), JSON.stringify(presets));
    return true;
  } catch {
    return false;
  }
}

/** Validate preset filters against current config, dropping invalid keys. */
function validatePreset(
  preset: Preset,
  configs: readonly FilterConfig[],
): { filters: FilterValues; droppedKeys: string[] } {
  const validKeys = new Set<string>();
  for (const c of configs) {
    switch (c.type) {
      case 'multi-select':
      case 'select':
        validKeys.add(c.key);
        break;
      case 'date-range':
        validKeys.add(c.urlKeys.from);
        validKeys.add(c.urlKeys.to);
        break;
      case 'range':
        validKeys.add(c.urlKeys.min);
        validKeys.add(c.urlKeys.max);
        break;
    }
  }

  const validated: FilterValues = {};
  const droppedKeys: string[] = [];
  for (const [key, value] of Object.entries(preset.filters)) {
    if (validKeys.has(key)) {
      validated[key] = value;
    } else {
      droppedKeys.push(key);
    }
  }
  return { filters: validated, droppedKeys };
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export default function PresetManager({
  pageKey,
  config,
  filters,
  onApply,
}: PresetManagerProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [presets, setPresets] = useState(() => loadPresets(pageKey));

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some(
      (v) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0),
    ),
    [filters],
  );

  const handleSave = useCallback(() => {
    const trimmed = nameInput.trim();
    if (!trimmed) return;

    // Deduplicate name
    let name = trimmed;
    const existingNames = new Set(presets.map((p) => p.name));
    let counter = 2;
    while (existingNames.has(name)) {
      name = `${trimmed} (${counter})`;
      counter++;
    }

    const newPreset: Preset = {
      id: generateId(),
      name,
      filters: { ...filters },
      createdAt: new Date().toISOString(),
    };
    const updated = [...presets, newPreset];
    if (savePresets(pageKey, updated)) {
      setPresets(updated);
      setNameInput('');
      setSaving(false);
    }
  }, [nameInput, presets, filters, pageKey]);

  const handleLoad = useCallback(
    (preset: Preset) => {
      const { filters: validated, droppedKeys } = validatePreset(preset, config);
      if (droppedKeys.length > 0) {
        console.warn(`Preset "${preset.name}" had stale keys dropped: ${droppedKeys.join(', ')}`);
      }
      onApply(validated);
      setOpen(false);
    },
    [config, onApply],
  );

  const handleDelete = useCallback(
    (id: string) => {
      const updated = presets.filter((p) => p.id !== id);
      savePresets(pageKey, updated);
      setPresets(updated);
    },
    [presets, pageKey],
  );

  return (
    <FilterPopover
      open={open}
      onOpenChange={(o) => { setOpen(o); if (!o) setSaving(false); }}
      trigger={
        <button className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[13px] bg-[rgba(168,85,247,0.12)] border border-[rgba(168,85,247,0.25)] text-[#c4b5fd] hover:bg-[rgba(168,85,247,0.2)] transition-colors">
          <span>📌</span>
          <span>Presets</span>
          {presets.length > 0 && (
            <span className="text-[11px] opacity-70">({presets.length})</span>
          )}
        </button>
      }
      minWidth={260}
    >
      <div className="text-[11px] uppercase tracking-wide text-text-dim px-1 mb-1.5">
        Saved Presets
      </div>

      {presets.length === 0 && !saving && (
        <div className="px-2 py-3 text-[12px] text-text-dim text-center">
          No saved presets yet
        </div>
      )}

      {presets.map((preset) => (
        <div
          key={preset.id}
          className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-bg-hover group cursor-pointer"
          onClick={() => handleLoad(preset)}
        >
          <div className="min-w-0">
            <div className="text-[13px] text-text-heading truncate">{preset.name}</div>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); handleDelete(preset.id); }}
            className="text-[12px] text-text-dim opacity-0 group-hover:opacity-100 hover:text-error ml-2 shrink-0"
          >
            ✕
          </button>
        </div>
      ))}

      {/* Save section */}
      {saving ? (
        <div className="mt-2 pt-2 border-t border-border">
          <input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') setSaving(false);
            }}
            placeholder="Preset name..."
            maxLength={30}
            autoFocus
            className="w-full bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body outline-none focus:border-running/50"
          />
          <div className="flex gap-2 mt-1.5">
            <button
              onClick={handleSave}
              disabled={!nameInput.trim()}
              className="px-2 py-1 text-[12px] bg-running/15 text-running-dim rounded hover:bg-running/25 disabled:opacity-40"
            >
              Save
            </button>
            <button
              onClick={() => setSaving(false)}
              className="px-2 py-1 text-[12px] text-text-dim hover:text-text-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        hasActiveFilters && (
          <button
            onClick={() => setSaving(true)}
            className="w-full mt-2 pt-2 border-t border-border text-[12px] text-running-dim hover:text-running text-center py-1"
          >
            Save current filters as preset
          </button>
        )
      )}
    </FilterPopover>
  );
}

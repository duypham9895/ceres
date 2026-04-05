import { useState, useEffect, useRef } from 'react';
import type { RangeFilterConfig } from '../types';

interface RangeEditorProps {
  readonly config: RangeFilterConfig;
  readonly minValue: number | null;
  readonly maxValue: number | null;
  readonly onChange: (min: number | null, max: number | null) => void;
}

export default function RangeEditor({
  config,
  minValue,
  maxValue,
  onChange,
}: RangeEditorProps) {
  const [localMin, setLocalMin] = useState(minValue !== null ? String(minValue) : '');
  const [localMax, setLocalMax] = useState(maxValue !== null ? String(maxValue) : '');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync from URL → local state
  useEffect(() => {
    setLocalMin(minValue !== null ? String(minValue) : '');
  }, [minValue]);
  useEffect(() => {
    setLocalMax(maxValue !== null ? String(maxValue) : '');
  }, [maxValue]);

  const commit = (minStr: string, maxStr: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const min = minStr ? parseFloat(minStr) : null;
      const max = maxStr ? parseFloat(maxStr) : null;
      const safeMin = min !== null && Number.isFinite(min) ? min : null;
      const safeMax = max !== null && Number.isFinite(max) ? max : null;
      onChange(safeMin, safeMax);
    }, config.debounceMs ?? 300);
  };

  const handleMinChange = (val: string) => {
    setLocalMin(val);
    commit(val, localMax);
  };

  const handleMaxChange = (val: string) => {
    setLocalMax(val);
    commit(localMin, val);
  };

  // Visual track
  const minPct = minValue !== null
    ? ((minValue - config.min) / (config.max - config.min)) * 100
    : 0;
  const maxPct = maxValue !== null
    ? ((maxValue - config.min) / (config.max - config.min)) * 100
    : 100;

  return (
    <div className="space-y-3">
      <div className="text-[11px] uppercase tracking-wide text-text-dim px-1">
        {config.label} ({config.suffix})
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={localMin}
          onChange={(e) => handleMinChange(e.target.value)}
          placeholder={String(config.min)}
          min={config.min}
          max={config.max}
          step={config.step}
          className="w-20 bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body text-center outline-none focus:border-running/50"
        />
        <div className="flex-1 h-1 bg-border rounded-full relative">
          <div
            className="absolute h-full bg-running rounded-full"
            style={{ left: `${minPct}%`, right: `${100 - maxPct}%` }}
          />
        </div>
        <input
          type="number"
          value={localMax}
          onChange={(e) => handleMaxChange(e.target.value)}
          placeholder={String(config.max)}
          min={config.min}
          max={config.max}
          step={config.step}
          className="w-20 bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body text-center outline-none focus:border-running/50"
        />
      </div>
      {(minValue !== null || maxValue !== null) && (
        <button
          onClick={() => { setLocalMin(''); setLocalMax(''); onChange(null, null); }}
          className="text-[11px] text-error/70 hover:text-error px-1"
        >
          Clear range
        </button>
      )}
    </div>
  );
}

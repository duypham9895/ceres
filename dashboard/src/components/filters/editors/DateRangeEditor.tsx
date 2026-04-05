import type { DateRangeFilterConfig } from '../types';

interface DateRangeEditorProps {
  readonly config: DateRangeFilterConfig;
  readonly fromValue: string | null;
  readonly toValue: string | null;
  readonly onChange: (from: string | null, to: string | null) => void;
}

function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function getPresetRange(preset: string): { from: string; to: string } {
  const now = new Date();
  const today = toIsoDate(now);

  switch (preset) {
    case 'today':
      return { from: today, to: today };
    case 'last_7_days': {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return { from: toIsoDate(d), to: today };
    }
    case 'last_30_days': {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      return { from: toIsoDate(d), to: today };
    }
    case 'this_month': {
      const first = new Date(now.getFullYear(), now.getMonth(), 1);
      return { from: toIsoDate(first), to: today };
    }
    default:
      return { from: today, to: today };
  }
}

const PRESET_LABELS: Record<string, string> = {
  today: 'Today',
  last_7_days: 'Last 7 days',
  last_30_days: 'Last 30 days',
  this_month: 'This month',
};

export default function DateRangeEditor({
  config,
  fromValue,
  toValue,
  onChange,
}: DateRangeEditorProps) {
  const applyPreset = (preset: string) => {
    const { from, to } = getPresetRange(preset);
    onChange(from, to);
  };

  const isPresetActive = (preset: string): boolean => {
    if (!fromValue || !toValue) return false;
    const { from, to } = getPresetRange(preset);
    return fromValue === from && toValue === to;
  };

  return (
    <div className="space-y-2">
      <div className="text-[11px] uppercase tracking-wide text-text-dim px-1">
        Date Range
      </div>
      <div className="flex flex-wrap gap-1">
        {config.presets.map((preset) => (
          <button
            key={preset}
            onClick={() => applyPreset(preset)}
            className={`px-2.5 py-1 rounded text-[12px] transition-colors ${
              isPresetActive(preset)
                ? 'bg-running/20 text-running-dim border border-running/30'
                : 'bg-bg-hover text-text-muted hover:bg-border hover:text-text-body'
            }`}
          >
            {PRESET_LABELS[preset] ?? preset}
          </button>
        ))}
      </div>
      <div className="text-[11px] text-text-dim px-1 pt-1">Or custom range:</div>
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={fromValue ?? ''}
          onChange={(e) => onChange(e.target.value || null, toValue)}
          className="flex-1 bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body outline-none focus:border-running/50"
        />
        <span className="text-[12px] text-text-dim">to</span>
        <input
          type="date"
          value={toValue ?? ''}
          onChange={(e) => onChange(fromValue, e.target.value || null)}
          className="flex-1 bg-bg-primary border border-border rounded px-2 py-1.5 text-[13px] text-text-body outline-none focus:border-running/50"
        />
      </div>
      {(fromValue || toValue) && (
        <button
          onClick={() => onChange(null, null)}
          className="text-[11px] text-error/70 hover:text-error px-1"
        >
          Clear dates
        </button>
      )}
    </div>
  );
}

import type { SelectFilterConfig } from '../types';

interface SelectEditorProps {
  readonly config: SelectFilterConfig;
  readonly value: string | null;
  readonly onChange: (value: string | null) => void;
}

export default function SelectEditor({
  config,
  value,
  onChange,
}: SelectEditorProps) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-text-dim px-1 mb-1.5">
        {config.label}
      </div>
      <div className="max-h-48 overflow-y-auto">
        {config.options.map((option) => {
          const selected = value === option.value;
          return (
            <button
              key={option.value}
              onClick={() => onChange(selected ? null : option.value)}
              className={`w-full text-left px-2 py-1.5 rounded text-[13px] transition-colors ${
                selected
                  ? 'bg-running/15 text-running-dim'
                  : 'text-text-secondary hover:bg-bg-hover'
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

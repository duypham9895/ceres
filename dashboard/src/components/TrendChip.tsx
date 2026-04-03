import clsx from 'clsx';

interface TrendChipProps {
  readonly value: number; // positive = up, negative = down, 0 = flat
  readonly suffix?: string; // default "%"
}

export default function TrendChip({ value, suffix = '%' }: TrendChipProps) {
  const isDown = value < 0;
  const isFlat = value === 0;
  const arrow = isFlat ? '→' : isDown ? '↓' : '↑';
  const display = isFlat ? '0' : Math.abs(value).toFixed(1);

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium',
        isFlat && 'bg-bg-hover text-text-dim',
        isDown && 'bg-success/10 text-success',
        !isFlat && !isDown && 'bg-error/10 text-error',
      )}
    >
      {arrow} {display}{suffix}
    </span>
  );
}

import clsx from 'clsx';

interface SparklineBarProps {
  readonly data: number[];
  readonly color?: string;
  readonly highlightLast?: boolean;
  readonly height?: number;
}

export default function SparklineBar({ data, color = '#4ade80', highlightLast = true, height = 24 }: SparklineBarProps) {
  if (data.length === 0) return null;
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-[2px]" style={{ height }}>
      {data.map((value, i) => {
        const barHeight = Math.max((value / max) * 100, 4);
        const isLast = i === data.length - 1;
        return (
          <div
            key={i}
            className="flex-1 rounded-t-sm min-w-[3px]"
            style={{
              height: `${barHeight}%`,
              backgroundColor: highlightLast && isLast ? color : `${color}33`,
            }}
          />
        );
      })}
    </div>
  );
}

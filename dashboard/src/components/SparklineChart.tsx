import { LineChart, Line, ResponsiveContainer } from 'recharts';

interface DataPoint {
  readonly date: string;
  readonly value: number;
}

interface SparklineChartProps {
  readonly data: readonly DataPoint[];
  readonly color?: string;
}

export default function SparklineChart({ data, color = '#7c3aed' }: SparklineChartProps) {
  if (data.length < 2) {
    return (
      <div className="h-8 flex items-center text-[10px] text-text-dim">
        Insufficient data
      </div>
    );
  }

  return (
    <div className="h-8 mt-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={[...data]}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

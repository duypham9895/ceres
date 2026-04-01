interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'gray';
}

const COLOR_MAP = {
  blue: 'bg-blue-50 text-blue-700',
  green: 'bg-green-50 text-green-700',
  red: 'bg-red-50 text-red-700',
  yellow: 'bg-yellow-50 text-yellow-700',
  gray: 'bg-gray-50 text-gray-700',
};

export default function StatsCard({ title, value, subtitle, color = 'blue' }: StatsCardProps) {
  return (
    <div className={`rounded-xl p-6 ${COLOR_MAP[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-sm mt-1 opacity-60">{subtitle}</p>}
    </div>
  );
}

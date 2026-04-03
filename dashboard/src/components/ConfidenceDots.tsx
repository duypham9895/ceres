interface ConfidenceDotsProps {
  readonly score: number; // 0-1
  readonly max?: number; // default 5
}

export default function ConfidenceDots({ score, max = 5 }: ConfidenceDotsProps) {
  const filled = Math.round(score * max);
  return (
    <div className="flex gap-[3px]">
      {Array.from({ length: max }, (_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i < filled ? 'bg-success' : 'bg-bg-hover'}`}
        />
      ))}
    </div>
  );
}

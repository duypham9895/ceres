export function SkeletonCard() {
  return <div className="bg-bg-card rounded-xl p-5 border border-border-light animate-pulse h-28" />;
}

export function SkeletonTable({ rows = 5 }: { readonly rows?: number }) {
  return (
    <div className="bg-bg-card rounded-xl border border-border-light p-4 space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-4 bg-bg-hover rounded animate-pulse" />
      ))}
    </div>
  );
}

export function SkeletonPanel() {
  return (
    <div className="bg-bg-card rounded-xl border border-border-light p-4 animate-pulse">
      <div className="h-3 bg-bg-hover rounded w-1/3 mb-3" />
      <div className="space-y-2">
        <div className="h-3 bg-bg-hover rounded w-full" />
        <div className="h-3 bg-bg-hover rounded w-2/3" />
        <div className="h-3 bg-bg-hover rounded w-4/5" />
      </div>
    </div>
  );
}

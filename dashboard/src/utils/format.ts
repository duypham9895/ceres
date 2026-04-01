export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay > 7) return date.toLocaleDateString();
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHour > 0) return `${diffHour}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return 'just now';
}

export function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatAmount(value: number | null): string {
  if (value == null) return '';
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

export function formatAmountRange(min: number | null, max: number | null): string {
  if (min == null && max == null) return '-';
  const minStr = formatAmount(min);
  const maxStr = formatAmount(max);
  if (min != null && max != null) return `${minStr} - ${maxStr}`;
  if (min != null) return `${minStr}+`;
  return `up to ${maxStr}`;
}

export function formatRange(min: number | null, max: number | null, suffix: string): string {
  if (min == null && max == null) return '-';
  if (min != null && max != null) return `${min}${suffix} - ${max}${suffix}`;
  if (min != null) return `${min}${suffix}+`;
  return `up to ${max}${suffix}`;
}

export function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatShortDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

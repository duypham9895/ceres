const STATUS_STYLES: Record<string, string> = {
  active: 'bg-success/15 text-success-dim',
  unreachable: 'bg-error/15 text-error-dim',
  blocked: 'bg-warning/15 text-warning-dim',
  unknown: 'bg-text-dim/15 text-text-dim',
  success: 'bg-success/15 text-success-dim',
  failed: 'bg-error/15 text-error-dim',
  running: 'bg-running/15 text-running-dim',
  partial: 'bg-warning/15 text-warning-dim',
  timeout: 'bg-error/15 text-error-dim',
};

export default function StatusBadge({ status }: { readonly status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.unknown}`}>
      {status}
    </span>
  );
}

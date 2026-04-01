const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  unreachable: 'bg-red-100 text-red-800',
  blocked: 'bg-yellow-100 text-yellow-800',
  unknown: 'bg-gray-100 text-gray-600',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  running: 'bg-blue-100 text-blue-800',
  partial: 'bg-yellow-100 text-yellow-800',
  timeout: 'bg-orange-100 text-orange-800',
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[status] || STATUS_STYLES.unknown}`}>
      {status}
    </span>
  );
}

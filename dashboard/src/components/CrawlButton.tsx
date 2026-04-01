import { useCrawl } from '../hooks/useCrawl';

interface CrawlButtonProps {
  agent: string;
  label: string;
  bank?: string;
  variant?: 'primary' | 'secondary';
}

export default function CrawlButton({ agent, label, bank, variant = 'primary' }: CrawlButtonProps) {
  const { triggerCrawl, isRunning, error } = useCrawl();
  const baseStyles = 'px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50';
  const styles = variant === 'primary'
    ? `${baseStyles} bg-blue-600 text-white hover:bg-blue-700`
    : `${baseStyles} bg-gray-100 text-gray-700 hover:bg-gray-200`;

  return (
    <div>
      <button onClick={() => triggerCrawl(agent, bank)} disabled={isRunning} className={styles}>
        {isRunning ? 'Running...' : label}
      </button>
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}

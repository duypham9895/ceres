import { useCrawl } from '../hooks/useCrawl';

interface CrawlButtonProps {
  agent: string;
  label: string;
  bank?: string;
  variant?: 'primary' | 'secondary';
}

export default function CrawlButton({ agent, label, bank, variant = 'primary' }: CrawlButtonProps) {
  const { triggerCrawl, isRunning, isTriggering, error } = useCrawl();
  const disabled = isRunning || isTriggering;

  const baseStyles = 'px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
  const styles = variant === 'primary'
    ? `${baseStyles} bg-blue-600 text-white hover:bg-blue-700`
    : `${baseStyles} bg-gray-100 text-gray-700 hover:bg-gray-200`;

  return (
    <div className="relative group">
      <button
        onClick={() => triggerCrawl(agent, bank)}
        disabled={disabled}
        className={styles}
      >
        {isTriggering ? 'Starting...' : label}
      </button>
      {isRunning && !isTriggering && (
        <span className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          A crawl is already running
        </span>
      )}
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}

import { useCrawl } from '../hooks/useCrawl';

interface CrawlButtonProps {
  agent: string;
  label: string;
  bank?: string;
  variant?: 'primary' | 'secondary';
}

export default function CrawlButton({ agent, label, bank, variant = 'primary' }: CrawlButtonProps) {
  const { triggerCrawl, isRunning, isTriggering, error } = useCrawl();
  // For per-bank buttons, only disable while this button is triggering.
  // For global buttons (no bank specified), also disable when any crawl is running.
  const disabled = bank ? isTriggering : (isRunning || isTriggering);

  const baseStyles = 'px-4 py-2 rounded-md font-medium text-[12px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
  const styles = variant === 'primary'
    ? `${baseStyles} bg-accent text-white hover:bg-accent/80`
    : `${baseStyles} bg-bg-hover text-text-secondary border border-border-light hover:text-text-body`;

  return (
    <div className="relative group">
      <button
        onClick={() => triggerCrawl(agent, bank)}
        disabled={disabled}
        className={styles}
      >
        {isTriggering ? 'Starting...' : label}
      </button>
      {isRunning && !isTriggering && !bank && (
        <span className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-border-light text-text-secondary text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
          A crawl is already running
        </span>
      )}
      {error && <p className="text-error text-xs mt-1">{error}</p>}
    </div>
  );
}

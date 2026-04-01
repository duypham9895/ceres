import { useEffect, useState } from 'react';
import { useCrawlStatus, type PipelineStep } from '../context/CrawlStatusContext';

function formatElapsed(startedAt: string): string {
  const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}

function formatTimeAgo(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function StepIcon({ status }: { status: PipelineStep['status'] }) {
  switch (status) {
    case 'done':
      return <span className="text-success transition-opacity duration-200">&#10003;</span>;
    case 'running':
      return <span className="text-running animate-pulse">&#9654;</span>;
    case 'failed':
      return <span className="text-error">&#10007;</span>;
    case 'skipped':
      return <span className="text-text-dim">&#9675;</span>;
    default:
      return <span className="text-text-dim">&#9675;</span>;
  }
}

function StepRow({ step }: { step: PipelineStep }) {
  const bankLabel = step.bankCount !== null && step.bankTotal !== null
    ? `${step.bankCount}/${step.bankTotal}`
    : step.status === 'running' ? '...' : '\u2014';

  return (
    <div className={`flex items-center justify-between py-1 text-sm ${
      step.status === 'running' ? 'text-running-dim font-medium' :
      step.status === 'done' ? 'text-text-secondary' :
      step.status === 'failed' ? 'text-error-dim' :
      'text-text-dim'
    }`}>
      <div className="flex items-center gap-2">
        <StepIcon status={step.status} />
        <span className="capitalize">{step.name}</span>
      </div>
      <span className="text-xs tabular-nums">{bankLabel}</span>
    </div>
  );
}

export default function CrawlPipelineMonitor() {
  const status = useCrawlStatus();
  const [elapsed, setElapsed] = useState('');

  useEffect(() => {
    if (!status.isRunning || !status.startedAt) {
      setElapsed('');
      return;
    }
    setElapsed(formatElapsed(status.startedAt));
    const interval = setInterval(() => {
      setElapsed(formatElapsed(status.startedAt!));
    }, 1000);
    return () => clearInterval(interval);
  }, [status.isRunning, status.startedAt]);

  if (!status.isRunning && status.steps.length === 0) {
    return (
      <div className="px-4 py-3 border-t border-b border-border bg-bg-primary/50">
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <span className="w-2 h-2 rounded-full bg-text-dim" />
          Ready
        </div>
        {status.lastCompletedCrawl && (
          <p className="text-xs text-text-dim mt-1">
            Last crawl: {formatTimeAgo(status.lastCompletedCrawl.finishedAt)} —{' '}
            {status.lastCompletedCrawl.successCount}/{status.lastCompletedCrawl.totalCount} OK
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="px-4 py-3 border-t border-b border-border bg-running/5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text-heading">
          {status.isRunning ? 'Crawl in Progress' : 'Crawl Complete'}
        </span>
        {elapsed && (
          <span className="text-xs text-text-muted tabular-nums">{elapsed}</span>
        )}
      </div>
      <div className="space-y-0.5">
        {status.steps.map((step) => (
          <StepRow key={step.name} step={step} />
        ))}
      </div>
      {status.failures > 0 && (
        <p className="text-xs text-warning mt-2">
          {status.failures} failure{status.failures !== 1 ? 's' : ''} so far
        </p>
      )}
    </div>
  );
}

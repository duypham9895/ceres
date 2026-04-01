import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LiveFeed from '../LiveFeed';
import type { CrawlEvent } from '../../hooks/useWebSocket';

function makeEvent(overrides: Partial<CrawlEvent> = {}): CrawlEvent {
  return {
    type: 'job_start',
    job_id: 'test-job-1',
    ...overrides,
  };
}

describe('LiveFeed', () => {
  it('renders event list with agent names and messages', () => {
    const events: CrawlEvent[] = [
      makeEvent({ type: 'job_start', agent: 'scout' }),
      makeEvent({ type: 'job_finish', agent: 'collector', job_id: 'job-2' }),
    ];

    render(<LiveFeed events={events} />);

    expect(screen.getByText('scout')).toBeInTheDocument();
    expect(screen.getByText('collector')).toBeInTheDocument();
    expect(screen.getByText('Started scout job')).toBeInTheDocument();
    expect(screen.getByText('Crawl completed')).toBeInTheDocument();
  });

  it('shows empty state "Waiting for crawl events..."', () => {
    render(<LiveFeed events={[]} />);

    expect(screen.getByText('Waiting for crawl events...')).toBeInTheDocument();
  });

  it('formats event types correctly', () => {
    const events: CrawlEvent[] = [
      makeEvent({ type: 'job_start', agent: 'scout' }),
      makeEvent({
        type: 'job_progress',
        step: 'Scraping',
        banks_processed: 5,
        banks_total: 10,
        job_id: 'job-2',
      }),
      makeEvent({ type: 'job_step_start', step: 'login', job_id: 'job-3' }),
      makeEvent({ type: 'job_error', error: 'Timeout reached', job_id: 'job-4' }),
    ];

    render(<LiveFeed events={events} />);

    expect(screen.getByText('Started scout job')).toBeInTheDocument();
    expect(screen.getByText('Scraping: 5/10 banks')).toBeInTheDocument();
    expect(screen.getByText('Running login')).toBeInTheDocument();
    expect(screen.getByText('Timeout reached')).toBeInTheDocument();

    // Type badges should strip "job_" prefix
    expect(screen.getByText('start')).toBeInTheDocument();
    expect(screen.getByText('progress')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
  });
});

import { useState } from 'react';
import { apiPost } from '../api/client';
import { useCrawlStatus } from '../context/CrawlStatusContext';

interface CrawlResponse {
  job_id: string;
  agent: string;
  status: string;
  started_at: string;
}

export function useCrawl() {
  const { isRunning } = useCrawlStatus();
  const [error, setError] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

  const triggerCrawl = async (agent: string, bank?: string) => {
    setError(null);
    setIsTriggering(true);
    try {
      const params = bank ? `?bank=${bank}` : '';
      await apiPost<CrawlResponse>(`/api/crawl/${agent}${params}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger crawl');
    } finally {
      setIsTriggering(false);
    }
  };

  const reset = () => setError(null);

  return { triggerCrawl, isRunning, isTriggering, error, reset };
}

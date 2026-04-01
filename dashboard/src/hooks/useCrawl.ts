import { useState } from 'react';
import { apiPost } from '../api/client';

interface CrawlResponse {
  job_id: string;
  agent: string;
  status: string;
  started_at: string;
}

export function useCrawl() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const triggerCrawl = async (agent: string, bank?: string) => {
    setError(null);
    setIsRunning(true);
    try {
      const params = bank ? `?bank=${bank}` : '';
      await apiPost<CrawlResponse>(`/api/crawl/${agent}${params}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger crawl');
      setIsRunning(false);
    }
  };

  const reset = () => {
    setIsRunning(false);
    setError(null);
  };

  return { triggerCrawl, isRunning, error, reset };
}

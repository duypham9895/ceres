import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useCrawlStatus } from '../context/CrawlStatusContext';

export default function CrawlToast() {
  const status = useCrawlStatus();
  const navigate = useNavigate();
  const prevRunning = useRef(status.isRunning);

  useEffect(() => {
    if (prevRunning.current && !status.isRunning && status.steps.length > 0) {
      const hasFailed = status.steps.some((s) => s.status === 'failed');
      const doneSteps = status.steps.filter((s) => s.status === 'done');
      const totalBanks = doneSteps.reduce((sum, s) => sum + (s.bankTotal ?? 0), 0);
      const successBanks = doneSteps.reduce((sum, s) => sum + (s.bankCount ?? 0), 0) - status.failures;

      if (hasFailed) {
        toast.error('Crawl Failed', {
          description: `Failed at ${status.steps.find((s) => s.status === 'failed')?.name ?? 'unknown'} step`,
          action: {
            label: 'View Logs',
            onClick: () => navigate('/logs'),
          },
          duration: 8000,
        });
      } else {
        toast.success('Crawl Complete', {
          description: totalBanks > 0
            ? `${successBanks}/${totalBanks} banks OK${status.failures > 0 ? ` \u2022 ${status.failures} failures` : ''}`
            : 'All steps completed',
          action: status.failures > 0
            ? { label: 'View Logs', onClick: () => navigate('/logs') }
            : undefined,
          duration: 8000,
        });
      }
    }
    prevRunning.current = status.isRunning;
  }, [status.isRunning, status.steps, status.failures, navigate]);

  return null;
}

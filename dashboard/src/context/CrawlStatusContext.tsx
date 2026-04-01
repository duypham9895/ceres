import { createContext, useContext, useEffect, useState, useRef, type ReactNode } from 'react';
import { useWebSocket, type CrawlEvent } from '../hooks/useWebSocket';
import { apiFetch } from '../api/client';

// --- Types ---

export interface PipelineStep {
  name: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  bankCount: number | null;
  bankTotal: number | null;
}

export interface LastCompletedCrawl {
  finishedAt: string;
  successCount: number;
  totalCount: number;
}

export interface CrawlStatus {
  isRunning: boolean;
  jobId: string | null;
  agent: string | null;
  currentStep: string | null;
  steps: PipelineStep[];
  startedAt: string | null;
  failures: number;
  lastCompletedCrawl: LastCompletedCrawl | null;
  isConnected: boolean;
}

const DAILY_STEPS = ['scout', 'strategist', 'crawler', 'parser'];

function buildPipelineSteps(agent: string): PipelineStep[] {
  if (agent === 'daily') {
    return DAILY_STEPS.map((name) => ({
      name,
      status: 'pending' as const,
      bankCount: null,
      bankTotal: null,
    }));
  }
  return [{ name: agent, status: 'pending', bankCount: null, bankTotal: null }];
}

const INITIAL_STATUS: CrawlStatus = {
  isRunning: false,
  jobId: null,
  agent: null,
  currentStep: null,
  steps: [],
  startedAt: null,
  failures: 0,
  lastCompletedCrawl: null,
  isConnected: false,
};

// --- Context ---

const CrawlStatusContext = createContext<CrawlStatus>(INITIAL_STATUS);

export function useCrawlStatus(): CrawlStatus {
  return useContext(CrawlStatusContext);
}

// --- Provider ---

interface StatusResponse {
  status: string;
  current_job: {
    job_id: string;
    agent: string;
    status: string;
    started_at: string;
    current_step?: string;
    step_index?: number;
    total_steps?: number;
  } | null;
  last_completed: {
    finished_at: string;
    success_count: number;
    total_count: number;
  } | null;
}

export function CrawlStatusProvider({ children }: { children: ReactNode }) {
  const { lastEvent, isConnected } = useWebSocket();
  const [status, setStatus] = useState<CrawlStatus>(INITIAL_STATUS);
  const hydrated = useRef(false);

  // Hydrate from /api/status on mount
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;

    apiFetch<StatusResponse>('/api/status').then((data) => {
      if (data.current_job) {
        const job = data.current_job;
        const steps = buildPipelineSteps(job.agent);
        const stepIndex = job.step_index ?? 0;
        const updatedSteps = steps.map((s, i) => {
          if (i < stepIndex) return { ...s, status: 'done' as const };
          if (i === stepIndex) return { ...s, status: 'running' as const };
          return s;
        });

        setStatus({
          isRunning: true,
          jobId: job.job_id,
          agent: job.agent,
          currentStep: job.current_step ?? steps[stepIndex]?.name ?? null,
          steps: updatedSteps,
          startedAt: job.started_at,
          failures: 0,
          lastCompletedCrawl: null,
          isConnected,
        });
      } else if (data.last_completed) {
        setStatus((prev) => ({
          ...prev,
          lastCompletedCrawl: {
            finishedAt: data.last_completed!.finished_at,
            successCount: data.last_completed!.success_count,
            totalCount: data.last_completed!.total_count,
          },
          isConnected,
        }));
      }
    }).catch(() => {
      // API unavailable — stay in initial state
    });
  }, [isConnected]);

  // Process WebSocket events
  useEffect(() => {
    if (!lastEvent) return;
    setStatus((prev) => processEvent(prev, lastEvent));
  }, [lastEvent]);

  // Keep isConnected in sync
  useEffect(() => {
    setStatus((prev) => prev.isConnected === isConnected ? prev : { ...prev, isConnected });
  }, [isConnected]);

  return (
    <CrawlStatusContext.Provider value={status}>
      {children}
    </CrawlStatusContext.Provider>
  );
}

// --- Event processor (pure function, no mutations) ---

function processEvent(prev: CrawlStatus, event: CrawlEvent): CrawlStatus {
  switch (event.type) {
    case 'job_start': {
      const steps = buildPipelineSteps(event.agent ?? 'daily');
      return {
        ...prev,
        isRunning: true,
        jobId: event.job_id,
        agent: event.agent ?? null,
        currentStep: steps[0]?.name ?? null,
        steps,
        startedAt: new Date().toISOString(),
        failures: 0,
        lastCompletedCrawl: null,
      };
    }

    case 'job_step_start': {
      const stepIndex = event.step_index ?? 0;
      const updatedSteps = prev.steps.map((s, i) => {
        if (i < stepIndex) return s.status === 'done' ? s : { ...s, status: 'done' as const };
        if (i === stepIndex) return { ...s, status: 'running' as const };
        return s;
      });
      return {
        ...prev,
        currentStep: event.step ?? null,
        steps: updatedSteps,
      };
    }

    case 'job_progress': {
      const stepIndex = event.step_index ?? 0;
      const banksFailed = event.banks_failed ?? 0;
      const updatedSteps = prev.steps.map((s, i) => {
        if (i === stepIndex) {
          return {
            ...s,
            status: 'done' as const,
            bankCount: event.banks_processed ?? null,
            bankTotal: event.banks_total ?? null,
          };
        }
        if (i === stepIndex + 1 && i < prev.steps.length) {
          return { ...s, status: 'running' as const };
        }
        return s;
      });
      return {
        ...prev,
        steps: updatedSteps,
        failures: prev.failures + banksFailed,
      };
    }

    case 'job_finish': {
      const finishedSteps = prev.steps.map((s) =>
        s.status !== 'done' ? { ...s, status: 'done' as const } : s
      );
      return {
        ...prev,
        isRunning: false,
        currentStep: null,
        steps: finishedSteps,
      };
    }

    case 'job_error': {
      const errorSteps = prev.steps.map((s) => {
        if (s.status === 'running') return { ...s, status: 'failed' as const };
        if (s.status === 'pending') return { ...s, status: 'skipped' as const };
        return s;
      });
      return {
        ...prev,
        isRunning: false,
        currentStep: null,
        steps: errorSteps,
      };
    }

    default:
      return prev;
  }
}

// Export for testing
export { processEvent, buildPipelineSteps };

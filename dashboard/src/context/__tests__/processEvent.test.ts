import { describe, it, expect } from 'vitest';
import { processEvent, buildPipelineSteps } from '../CrawlStatusContext';
import type { CrawlStatus } from '../CrawlStatusContext';
import type { CrawlEvent } from '../../hooks/useWebSocket';

const INITIAL: CrawlStatus = {
  isRunning: false,
  jobId: null,
  agent: null,
  currentStep: null,
  steps: [],
  startedAt: null,
  failures: 0,
  lastCompletedCrawl: null,
  isConnected: true,
};

describe('buildPipelineSteps', () => {
  it('builds 4 steps for daily agent', () => {
    const steps = buildPipelineSteps('daily');
    expect(steps).toHaveLength(4);
    expect(steps.map(s => s.name)).toEqual(['scout', 'strategist', 'crawler', 'learning']);
    expect(steps.every(s => s.status === 'pending')).toBe(true);
  });

  it('builds 1 step for single agent', () => {
    const steps = buildPipelineSteps('scout');
    expect(steps).toHaveLength(1);
    expect(steps[0].name).toBe('scout');
  });
});

describe('processEvent', () => {
  it('job_start initializes pipeline', () => {
    const event: CrawlEvent = { type: 'job_start', job_id: '123', agent: 'daily' };
    const result = processEvent(INITIAL, event);
    expect(result.isRunning).toBe(true);
    expect(result.jobId).toBe('123');
    expect(result.steps).toHaveLength(4);
    expect(result.currentStep).toBe('scout');
  });

  it('job_step_start marks current step as running', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const event: CrawlEvent = { type: 'job_step_start', job_id: '1', step: 'strategist', step_index: 1, total_steps: 4 };
    const result = processEvent(running, event);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[1].status).toBe('running');
    expect(result.currentStep).toBe('strategist');
  });

  it('job_progress marks step as done with bank counts', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const stepped = processEvent(running, { type: 'job_step_start', job_id: '1', step: 'scout', step_index: 0, total_steps: 4 });
    const event: CrawlEvent = { type: 'job_progress', job_id: '1', step: 'scout', step_index: 0, total_steps: 4, banks_processed: 55, banks_total: 58, banks_failed: 3 };
    const result = processEvent(stepped, event);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[0].bankCount).toBe(55);
    expect(result.steps[0].bankTotal).toBe(58);
    expect(result.failures).toBe(3);
  });

  it('job_finish marks all steps done', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const event: CrawlEvent = { type: 'job_finish', job_id: '1', agent: 'daily' };
    const result = processEvent(running, event);
    expect(result.isRunning).toBe(false);
    expect(result.steps.every(s => s.status === 'done')).toBe(true);
  });

  it('job_error marks running step as failed, pending as skipped', () => {
    const running = processEvent(INITIAL, { type: 'job_start', job_id: '1', agent: 'daily' });
    const stepped = processEvent(running, { type: 'job_step_start', job_id: '1', step: 'crawler', step_index: 2, total_steps: 4 });
    const event: CrawlEvent = { type: 'job_error', job_id: '1', agent: 'daily', error: 'timeout' };
    const result = processEvent(stepped, event);
    expect(result.isRunning).toBe(false);
    expect(result.steps[0].status).toBe('done');
    expect(result.steps[1].status).toBe('done');
    expect(result.steps[2].status).toBe('failed');
    expect(result.steps[3].status).toBe('skipped');
  });

  it('single agent job_start creates one step', () => {
    const event: CrawlEvent = { type: 'job_start', job_id: '1', agent: 'scout' };
    const result = processEvent(INITIAL, event);
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].name).toBe('scout');
  });

  it('unknown event type returns state unchanged', () => {
    const event: CrawlEvent = { type: 'unknown_event', job_id: '1' };
    const result = processEvent(INITIAL, event);
    expect(result).toBe(INITIAL);
  });
});

-- Migration: Add job_id column to agent_runs for linking arq jobs to DB records
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS job_id TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_runs_job_id ON agent_runs(job_id) WHERE job_id IS NOT NULL;

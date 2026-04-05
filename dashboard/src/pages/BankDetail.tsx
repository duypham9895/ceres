import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiFetch, apiPost } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import CrawlButton from '../components/CrawlButton';
import CompletenessBar from '../components/CompletenessBar';
import { formatDate, formatRelativeTime } from '../utils/format';

interface BankInfo {
  id: string;
  bank_code: string;
  bank_name: string;
  bank_category: string;
  bank_type: string;
  website_url: string;
  website_status: string;
  last_crawled_at: string | null;
  crawl_streak: number;
  success_rate_30d: number;
  avg_quality: number;
  avg_confidence: number;
}

interface Strategy {
  bypass_method: string;
  success_rate: number;
  version: string;
  anti_bot_type: string | null;
}

interface LoanProgram {
  id: number;
  program_name: string;
  loan_type: string;
  min_interest_rate: number | null;
  max_interest_rate: number | null;
  updated_at: string;
}

interface CrawlLog {
  id: number;
  pages_crawled: number | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

interface PipelineStatus {
  crawl: { status: 'never' | 'running' | 'success' | 'failed'; pages: number; last_run: string | null };
  parse: { total: number; parsed: number; unparsed: number };
  extract: { programs: number };
}

interface BankDetailData {
  bank: BankInfo;
  strategy: Strategy | null;
  programs: LoanProgram[];
  crawl_logs: CrawlLog[];
  pipeline_status?: PipelineStatus;
}

function InfoItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-text-heading">{children}</dd>
    </div>
  );
}

type StepState = 'success' | 'error' | 'warning' | 'idle' | 'running';

function PipelineStep({
  label,
  state,
  detail,
  message,
  action,
}: {
  label: string;
  state: StepState;
  detail: string;
  message?: string;
  action?: React.ReactNode;
}) {
  const icons: Record<StepState, string> = {
    success: '✔',
    error: '✖',
    warning: '~',
    idle: '–',
    running: '⟳',
  };
  const colors: Record<StepState, string> = {
    success: 'text-green-400',
    error: 'text-red-400',
    warning: 'text-amber-400',
    idle: 'text-text-muted',
    running: 'text-blue-400 animate-spin inline-block',
  };

  return (
    <div className="flex items-start gap-3 py-2">
      <span className={`text-sm font-bold w-4 shrink-0 ${colors[state]}`}>{icons[state]}</span>
      <span className="text-sm font-medium text-text-heading w-16 shrink-0">{label}</span>
      <span className="text-sm text-text-secondary">{detail}</span>
      {message && <span className="text-sm text-text-muted italic ml-2">{message}</span>}
      {action && <span className="ml-auto">{action}</span>}
    </div>
  );
}

function derivePipelineSteps(ps: PipelineStatus): {
  crawlState: StepState; crawlDetail: string; crawlMsg?: string;
  parseState: StepState; parseDetail: string; parseMsg?: string;
  extractState: StepState; extractDetail: string; extractMsg?: string;
} {
  const { crawl, parse, extract } = ps;

  // Crawl step
  const crawlState: StepState =
    crawl.status === 'never' ? 'idle'
    : crawl.status === 'running' ? 'running'
    : crawl.status === 'failed' ? 'error'
    : 'success';
  const crawlDetail =
    crawl.status === 'never' ? 'Never crawled'
    : crawl.status === 'running' ? 'In progress…'
    : crawl.status === 'failed' ? `Failed${crawl.last_run ? ` · ${formatDate(crawl.last_run)}` : ''}`
    : `${crawl.pages} page${crawl.pages !== 1 ? 's' : ''} · ${formatDate(crawl.last_run)}`;
  const crawlMsg = crawl.status === 'never' ? 'Bank has never been crawled' : undefined;

  // Parse step — only meaningful after a successful crawl
  const parseReady = crawl.status === 'success' || parse.total > 0;
  const parseState: StepState =
    !parseReady ? 'idle'
    : crawl.status === 'running' ? 'idle'
    : parse.total === 0 ? 'error'
    : parse.unparsed === 0 ? 'success'
    : 'warning';
  const parseDetail =
    !parseReady ? '–'
    : parse.total === 0 ? '0 pages'
    : `${parse.parsed}/${parse.total} parsed`;
  const parseMsg =
    parseState === 'error' ? 'Parser has not run yet'
    : parseState === 'warning' ? `${parse.unparsed} page${parse.unparsed !== 1 ? 's' : ''} not yet parsed`
    : undefined;

  // Extract step — only meaningful after parsing
  const extractReady = parse.parsed > 0;
  const extractState: StepState =
    !extractReady ? 'idle'
    : extract.programs > 0 ? 'success'
    : 'error';
  const extractDetail =
    !extractReady ? '–'
    : `${extract.programs} program${extract.programs !== 1 ? 's' : ''}`;
  const extractMsg =
    extractState === 'error' ? 'LLM returned 0 programs'
    : undefined;

  return {
    crawlState, crawlDetail, crawlMsg,
    parseState, parseDetail, parseMsg,
    extractState, extractDetail, extractMsg,
  };
}

export default function BankDetail() {
  const { id } = useParams<{ id: string }>();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['bank', id],
    queryFn: () => apiFetch<BankDetailData>(`/api/banks/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-text-muted">Loading bank details...</p>;
  if (isError) return <p className="text-error">Error: {error instanceof Error ? error.message : 'Failed to load bank'}</p>;
  if (!data) return null;

  const { bank, strategy, programs, crawl_logs, pipeline_status } = data;

  const pipelineSteps = pipeline_status ? derivePipelineSteps(pipeline_status) : null;

  return (
    <div className="space-y-6">
      {/* Header with CTA buttons */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-text-heading">{bank.bank_name}</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              apiPost(`/api/crawl/learning?bank=${bank.bank_code}`)
                .then(() => toast.success('Learning triggered'))
                .catch(() => toast.error('Failed to trigger learning'))
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20"
          >
            Re-learn Strategy
          </button>
          <CrawlButton agent="daily" label="Crawl This Bank" bank={bank.bank_code} />
        </div>
      </div>

      {/* 3 Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Crawl Health card */}
        <div className="bg-bg-card rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-text-heading mb-3">Crawl Health</h3>
          <dl className="space-y-2">
            <InfoItem label="Success rate (30d)">
              <span className="font-[var(--font-mono)]">
                {Math.round((bank.success_rate_30d ?? 0) * 100)}%
              </span>
            </InfoItem>
            <InfoItem label="Crawl streak">
              <span>🔥 {bank.crawl_streak ?? 0}</span>
            </InfoItem>
            <InfoItem label="Last crawled">
              {bank.last_crawled_at ? formatRelativeTime(bank.last_crawled_at) : '–'}
            </InfoItem>
            <InfoItem label="Total crawls">{crawl_logs.length}</InfoItem>
          </dl>
        </div>

        {/* Strategy card */}
        <div className="bg-bg-card rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-text-heading mb-3">Strategy</h3>
          {strategy ? (
            <dl className="space-y-2">
              <InfoItem label="Bypass method">{strategy.bypass_method}</InfoItem>
              <InfoItem label="Version">{strategy.version}</InfoItem>
              <InfoItem label="Success rate">
                <div className="flex items-center gap-2">
                  <span className="font-[var(--font-mono)] text-xs">
                    {Math.round(strategy.success_rate * 100)}%
                  </span>
                  <CompletenessBar score={strategy.success_rate} width={80} />
                </div>
              </InfoItem>
              {strategy.anti_bot_type && (
                <InfoItem label="Anti-bot">
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-warning/10 text-warning border border-warning/20">
                    {strategy.anti_bot_type}
                  </span>
                </InfoItem>
              )}
            </dl>
          ) : (
            <p className="text-sm text-text-muted">No strategy configured</p>
          )}
        </div>

        {/* Data Quality card */}
        <div className="bg-bg-card rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-text-heading mb-3">Data Quality</h3>
          <dl className="space-y-2">
            <InfoItem label="Avg completeness">
              <CompletenessBar score={bank.avg_quality ?? 0} width={100} />
            </InfoItem>
            <InfoItem label="Program count">{programs.length}</InfoItem>
            <InfoItem label="Avg confidence">
              <span className="font-[var(--font-mono)]">
                {Math.round((bank.avg_confidence ?? 0) * 100)}%
              </span>
            </InfoItem>
            <InfoItem label="Website">
              <StatusBadge status={bank.website_status} />
            </InfoItem>
          </dl>
        </div>
      </div>

      {/* Bank Info Card */}
      <div className="bg-bg-card rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-text-heading mb-4">Bank Information</h3>
        <dl className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <InfoItem label="Code">{bank.bank_code}</InfoItem>
          <InfoItem label="Name">{bank.bank_name}</InfoItem>
          <InfoItem label="Category">{bank.bank_category}</InfoItem>
          <InfoItem label="Type">{bank.bank_type}</InfoItem>
          <InfoItem label="Website">
            <a href={bank.website_url} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">
              {bank.website_url}
            </a>
          </InfoItem>
          <InfoItem label="Status"><StatusBadge status={bank.website_status} /></InfoItem>
        </dl>
      </div>

      {/* Pipeline Status Card */}
      {pipelineSteps && (
        <div className="bg-bg-card rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-text-heading">Pipeline Status</h3>
            {pipelineSteps.parseState === 'success' && pipelineSteps.extractState === 'error' && (
              <CrawlButton agent="parser" label="Re-parse" bank={bank.bank_code} variant="secondary" />
            )}
          </div>
          <div className="divide-y divide-border">
            <PipelineStep
              label="Crawl"
              state={pipelineSteps.crawlState}
              detail={pipelineSteps.crawlDetail}
              message={pipelineSteps.crawlMsg}
              action={
                pipelineSteps.crawlState === 'error' ? (
                  <button
                    onClick={() =>
                      apiPost(`/api/crawl/crawler?bank=${bank.bank_code}`)
                        .then(() => toast.success('Re-crawl triggered'))
                        .catch(() => toast.error('Failed to trigger re-crawl'))
                    }
                    className="text-xs font-medium text-accent hover:text-accent/80 border border-accent/20 rounded px-2 py-0.5"
                  >
                    Re-crawl
                  </button>
                ) : undefined
              }
            />
            <PipelineStep
              label="Parse"
              state={pipelineSteps.parseState}
              detail={pipelineSteps.parseDetail}
              message={pipelineSteps.parseMsg}
              action={
                pipelineSteps.parseState === 'error' ? (
                  <button
                    onClick={() =>
                      apiPost(`/api/crawl/parser?bank=${bank.bank_code}`)
                        .then(() => toast.success('Re-parse triggered'))
                        .catch(() => toast.error('Failed to trigger re-parse'))
                    }
                    className="text-xs font-medium text-accent hover:text-accent/80 border border-accent/20 rounded px-2 py-0.5"
                  >
                    Re-parse
                  </button>
                ) : undefined
              }
            />
            <PipelineStep
              label="Extract"
              state={pipelineSteps.extractState}
              detail={pipelineSteps.extractDetail}
              message={pipelineSteps.extractMsg}
            />
          </div>
        </div>
      )}

      {/* Loan Programs Table */}
      <div className="bg-bg-card rounded-lg shadow">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-text-heading">Loan Programs ({programs.length})</h3>
        </div>
        {programs.length === 0 ? (
          <p className="px-6 py-4 text-sm text-text-muted">No loan programs found.</p>
        ) : (
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-bg-card">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Program</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Interest Rate</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {programs.map((program) => (
                <tr key={program.id} className="hover:bg-bg-hover">
                  <td className="px-4 py-3 text-sm text-text-heading">{program.program_name}</td>
                  <td className="px-4 py-3 text-sm text-text-secondary">{program.loan_type}</td>
                  <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-heading">
                    {program.min_interest_rate != null && program.max_interest_rate != null
                      ? `${program.min_interest_rate}% - ${program.max_interest_rate}%`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-secondary">{formatDate(program.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Crawl History Table */}
      <div className="bg-bg-card rounded-lg shadow">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-text-heading">Crawl History</h3>
        </div>
        {crawl_logs.length === 0 ? (
          <p className="px-6 py-4 text-sm text-text-muted">No crawl logs found.</p>
        ) : (
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-bg-card">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Pages</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Started</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Finished</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Error</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {crawl_logs.map((log) => (
                <tr key={log.id} className="hover:bg-bg-hover">
                  <td className="px-4 py-3 text-sm font-[var(--font-mono)] text-text-secondary">{log.pages_crawled ?? '-'}</td>
                  <td className="px-4 py-3 text-sm"><StatusBadge status={log.status} /></td>
                  <td className="px-4 py-3 text-sm text-text-secondary">{formatDate(log.started_at)}</td>
                  <td className="px-4 py-3 text-sm text-text-secondary">{formatDate(log.finished_at)}</td>
                  <td className="px-4 py-3 text-sm text-error">{log.error_message || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    {(log.status === 'failed' || log.status === 'blocked') && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          apiPost(`/api/crawl/crawler?bank=${bank.bank_code}`)
                            .then(() => toast.success('Re-crawl triggered'))
                            .catch(() => toast.error('Failed to trigger re-crawl'));
                        }}
                        className="text-[10px] font-medium text-accent hover:text-accent/80"
                      >
                        Re-crawl
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

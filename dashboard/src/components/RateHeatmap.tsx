import { useNavigate } from 'react-router-dom';

export interface HeatmapBank {
  readonly bank_id: string;
  readonly bank_code: string;
  readonly bank_name: string;
  readonly website_status: string;
  readonly rates: Readonly<Record<string, number>>;
}

const LOAN_COLUMNS = ['KPR', 'KPA', 'MULTIGUNA', 'KENDARAAN', 'MODAL_KERJA'] as const;

function rateColor(rate: number): string {
  if (rate < 8) return 'bg-rate-low text-success-dim';
  if (rate <= 10) return 'bg-rate-mid text-warning-dim';
  return 'bg-rate-high text-error-dim';
}

function StatusDot({ status }: { readonly status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-success/15 text-success-dim',
    unreachable: 'bg-error/15 text-error-dim',
    blocked: 'bg-warning/15 text-warning-dim',
    unknown: 'bg-text-dim/15 text-text-dim',
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors[status] ?? colors.unknown}`}>
      {status}
    </span>
  );
}

export default function RateHeatmap({ banks }: { readonly banks: readonly HeatmapBank[] }) {
  const navigate = useNavigate();

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-text-body">Rate Intelligence — All Banks</h3>
        <div className="flex items-center gap-1 text-[10px] text-text-muted">
          Low
          <span className="w-16 h-1.5 rounded-full bg-gradient-to-r from-success via-warning to-error" />
          High
        </div>
      </div>
      <div className="max-h-[360px] overflow-y-auto scrollbar-thin">
        <table className="w-full border-collapse text-[11px]">
          <thead>
            <tr>
              <th className="px-3 py-2 text-left text-[10px] font-semibold text-text-muted uppercase tracking-wider border-b border-border sticky top-0 bg-bg-card w-36">
                Bank
              </th>
              {LOAN_COLUMNS.map((col) => (
                <th key={col} className="px-2 py-2 text-center text-[10px] font-semibold text-text-muted uppercase tracking-wider border-b border-border sticky top-0 bg-bg-card">
                  {col.replace('_', ' ')}
                </th>
              ))}
              <th className="px-2 py-2 text-center text-[10px] font-semibold text-text-muted uppercase tracking-wider border-b border-border sticky top-0 bg-bg-card">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {banks.map((bank) => (
              <tr
                key={bank.bank_code}
                onClick={() => navigate(`/banks/${bank.bank_id}`)}
                className="hover:bg-bg-hover cursor-pointer border-b border-border/50"
              >
                <td className="px-3 py-1.5 text-text-body font-medium">{bank.bank_name}</td>
                {LOAN_COLUMNS.map((col) => {
                  const rate = bank.rates[col];
                  return (
                    <td key={col} className="px-2 py-1.5 text-center font-mono">
                      {rate != null ? (
                        <span className={`px-1.5 py-0.5 rounded ${rateColor(rate)}`}>
                          {rate.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-text-dim">—</span>
                      )}
                    </td>
                  );
                })}
                <td className="px-2 py-1.5 text-center">
                  <StatusDot status={bank.website_status} />
                </td>
              </tr>
            ))}
            {banks.length === 0 && (
              <tr>
                <td colSpan={LOAN_COLUMNS.length + 2} className="px-4 py-8 text-center text-text-muted">
                  No bank data available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

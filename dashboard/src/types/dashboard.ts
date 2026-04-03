export interface DashboardAlert {
  readonly category: string;
  readonly type: string;
  readonly message: string;
  readonly count: number;
  readonly bank_codes: readonly string[];
  readonly cta: {
    readonly label: string;
    readonly agent: string;
  };
}

export interface AlertsResponse {
  readonly total: number;
  readonly alerts: readonly DashboardAlert[];
}

export interface DashboardChange {
  readonly type: string;
  readonly count: number;
  readonly detail: string;
}

export interface ChangesResponse {
  readonly date: string;
  readonly changes: readonly DashboardChange[];
}

export interface QualityResponse {
  readonly high: {
    readonly count: number;
    readonly threshold: number;
  };
  readonly medium: {
    readonly count: number;
    readonly threshold: number;
  };
  readonly low: {
    readonly count: number;
    readonly threshold: number;
  };
  readonly avg_completeness: number;
}

export interface CrawlAnalytics {
  readonly stats: {
    readonly total_crawls_7d: number;
    readonly success_rate: number;
    readonly success_rate_prev_week: number;
    readonly avg_duration_ms: number;
    readonly programs_found: number;
    readonly programs_new: number;
  };
  readonly error_breakdown: Record<string, number>;
  readonly daily_success_rate: ReadonlyArray<{
    readonly date: string;
    readonly rate: number;
  }>;
}

export interface CompareProgram {
  readonly bank_code: string;
  readonly bank_name: string;
  readonly min_interest_rate: number | null;
  readonly max_interest_rate: number | null;
  readonly rate_fixed: number | null;
  readonly rate_floating: number | null;
  readonly rate_promo: number | null;
  readonly rate_promo_duration_months: number | null;
  readonly completeness_score: number;
}

export interface CompareResponse {
  readonly loan_type: string;
  readonly programs: readonly CompareProgram[];
}

export interface ExtendedDashboard {
  readonly total_banks: number;
  readonly total_programs: number;
  readonly banks_by_status: Record<string, number>;
  readonly success_rate: number;
  readonly crawl_stats: Record<string, number>;
  readonly quality_avg: number;
  readonly deltas: {
    readonly banks_week: number;
    readonly programs_new: number;
    readonly kpr_rate_change: number;
    readonly quality_change: number;
  };
  readonly sparklines: {
    readonly banks: readonly number[];
    readonly programs: readonly number[];
    readonly kpr_rate: readonly number[];
    readonly quality: readonly number[];
  };
}

export interface HeatmapBank {
  readonly bank_code: string;
  readonly bank_name: string;
  readonly website_status: string;
  readonly rates: Record<string, number | null>;
  readonly completeness_score: number;
  readonly data_confidence: number;
  readonly trend_7d: number | null;
}

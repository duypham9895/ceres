import type { FilterConfig } from '../components/filters/types';

export const LOAN_TYPES = [
  'KPR', 'KPA', 'KPT', 'MULTIGUNA', 'KENDARAAN', 'MODAL_KERJA',
  'INVESTASI', 'PENDIDIKAN', 'PMI', 'TAKE_OVER', 'REFINANCING', 'OTHER',
] as const;

export const LOAN_TYPE_LABELS: Record<string, string> = {
  KPR: 'KPR (Mortgage)',
  KPA: 'KPA (Apartment)',
  KPT: 'KPT (Land)',
  MULTIGUNA: 'Multiguna',
  KENDARAAN: 'Kendaraan (Vehicle)',
  MODAL_KERJA: 'Modal Kerja (Working Capital)',
  INVESTASI: 'Investasi',
  PENDIDIKAN: 'Pendidikan (Education)',
  PMI: 'PMI (Migrant Worker)',
  TAKE_OVER: 'Take Over',
  REFINANCING: 'Refinancing',
  OTHER: 'Other',
};

export const CRAWL_STATUSES = [
  'success', 'failed', 'blocked', 'timeout', 'partial',
] as const;

export const BANK_CATEGORIES = [
  'BUMN', 'SWASTA_NASIONAL', 'BPD', 'ASING', 'SYARIAH',
] as const;

export const BANK_CATEGORY_LABELS: Record<string, string> = {
  BUMN: 'BUMN (State-owned)',
  SWASTA_NASIONAL: 'Swasta Nasional',
  BPD: 'BPD (Regional)',
  ASING: 'Asing (Foreign)',
  SYARIAH: 'Syariah (Islamic)',
};

export const LOAN_PROGRAM_FILTERS: readonly FilterConfig[] = [
  {
    key: 'loan_type',
    label: 'Loan Type',
    type: 'multi-select',
    options: LOAN_TYPES.map((t) => ({ value: t, label: LOAN_TYPE_LABELS[t] ?? t })),
  },
  {
    key: 'bank_id',
    label: 'Bank',
    type: 'multi-select',
    optionsEndpoint: '/api/banks',
    optionLabelKey: 'bank_name',
    optionValueKey: 'id',
  },
  {
    key: 'date',
    label: 'Date',
    type: 'date-range',
    urlKeys: { from: 'date_from', to: 'date_to' },
    presets: ['today', 'last_7_days', 'last_30_days', 'this_month'],
  },
  {
    key: 'rate',
    label: 'Interest Rate',
    type: 'range',
    urlKeys: { min: 'rate_min', max: 'rate_max' },
    min: 0,
    max: 30,
    step: 0.5,
    suffix: '%',
    debounceMs: 300,
  },
  {
    key: 'sort',
    label: 'Sort',
    type: 'select',
    excludeFromClearAll: true,
    options: [
      { value: 'program_name', label: 'Program Name' },
      { value: 'min_interest_rate', label: 'Lowest Rate' },
      { value: 'data_confidence', label: 'Highest Confidence' },
      { value: 'completeness_score', label: 'Completeness' },
      { value: 'created_at', label: 'Newest First' },
    ],
  },
];

export const CRAWL_LOG_FILTERS: readonly FilterConfig[] = [
  {
    key: 'status',
    label: 'Status',
    type: 'multi-select',
    options: CRAWL_STATUSES.map((s) => ({
      value: s,
      label: s.charAt(0).toUpperCase() + s.slice(1),
    })),
  },
  {
    key: 'bank_id',
    label: 'Bank',
    type: 'multi-select',
    optionsEndpoint: '/api/banks',
    optionLabelKey: 'bank_name',
    optionValueKey: 'id',
  },
  {
    key: 'date',
    label: 'Date',
    type: 'date-range',
    urlKeys: { from: 'date_from', to: 'date_to' },
    presets: ['today', 'last_7_days', 'last_30_days', 'this_month'],
  },
];

export const BANK_FILTERS: readonly FilterConfig[] = [
  {
    key: 'category',
    label: 'Category',
    type: 'multi-select',
    options: BANK_CATEGORIES.map((c) => ({
      value: c,
      label: BANK_CATEGORY_LABELS[c] ?? c,
    })),
  },
  {
    key: 'website_status',
    label: 'Status',
    type: 'multi-select',
    options: [
      { value: 'active', label: 'Active' },
      { value: 'blocked', label: 'Blocked' },
      { value: 'unreachable', label: 'Unreachable' },
    ],
  },
];

export const STRATEGY_FILTERS: readonly FilterConfig[] = [
  {
    key: 'bank_id',
    label: 'Bank',
    type: 'multi-select',
    optionsEndpoint: '/api/banks',
    optionLabelKey: 'bank_name',
    optionValueKey: 'id',
  },
  {
    key: 'success_rate',
    label: 'Success Rate',
    type: 'range',
    urlKeys: { min: 'success_rate_min', max: 'success_rate_max' },
    min: 0,
    max: 100,
    step: 5,
    suffix: '%',
    debounceMs: 300,
  },
];

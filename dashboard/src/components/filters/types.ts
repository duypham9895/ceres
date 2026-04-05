export interface FilterOption {
  readonly value: string;
  readonly label: string;
}

export interface BaseFilterConfig {
  readonly key: string;
  readonly label: string;
}

export interface MultiSelectFilterConfig extends BaseFilterConfig {
  readonly type: 'multi-select';
  readonly options?: readonly FilterOption[];
  readonly optionsEndpoint?: string;
  readonly optionLabelKey?: string;
  readonly optionValueKey?: string;
}

export interface DateRangeFilterConfig extends BaseFilterConfig {
  readonly type: 'date-range';
  readonly urlKeys: { readonly from: string; readonly to: string };
  readonly presets: readonly string[];
}

export interface RangeFilterConfig extends BaseFilterConfig {
  readonly type: 'range';
  readonly urlKeys: { readonly min: string; readonly max: string };
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly suffix: string;
  readonly debounceMs?: number;
}

export interface SelectFilterConfig extends BaseFilterConfig {
  readonly type: 'select';
  readonly options: readonly FilterOption[];
  readonly excludeFromClearAll?: boolean;
}

export type FilterConfig =
  | MultiSelectFilterConfig
  | DateRangeFilterConfig
  | RangeFilterConfig
  | SelectFilterConfig;

export type FilterValues = Record<string, string | string[] | number | null>;

export interface Preset {
  readonly id: string;
  readonly name: string;
  readonly filters: FilterValues;
  readonly createdAt: string;
}

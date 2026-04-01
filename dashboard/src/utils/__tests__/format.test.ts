import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatDuration,
  formatAmount,
  formatRange,
} from '../format';

describe('formatDate', () => {
  it('returns locale string for valid ISO string', () => {
    const result = formatDate('2025-06-15T10:30:00Z');
    // Should produce a non-empty locale string (exact format is locale-dependent)
    expect(result).toBeTruthy();
    expect(result).not.toBe('-');
  });

  it('returns "-" for null', () => {
    expect(formatDate(null)).toBe('-');
  });

  it('returns "-" for empty string', () => {
    expect(formatDate('')).toBe('-');
  });
});

describe('formatDuration', () => {
  it('returns seconds string for ms value', () => {
    expect(formatDuration(1500)).toBe('1.5s');
    expect(formatDuration(10000)).toBe('10.0s');
    expect(formatDuration(500)).toBe('0.5s');
  });

  it('returns "-" for null', () => {
    expect(formatDuration(null)).toBe('-');
  });
});

describe('formatAmount', () => {
  it('returns empty string for null', () => {
    expect(formatAmount(null)).toBe('');
  });

  it('handles values below 1,000', () => {
    expect(formatAmount(500)).toBe('500');
    expect(formatAmount(0)).toBe('0');
  });

  it('handles K threshold (>= 1,000)', () => {
    expect(formatAmount(1000)).toBe('1K');
    expect(formatAmount(5500)).toBe('6K');
  });

  it('handles M threshold (>= 1,000,000)', () => {
    expect(formatAmount(1_000_000)).toBe('1.0M');
    expect(formatAmount(2_500_000)).toBe('2.5M');
  });

  it('handles B threshold (>= 1,000,000,000)', () => {
    expect(formatAmount(1_000_000_000)).toBe('1.0B');
    expect(formatAmount(3_700_000_000)).toBe('3.7B');
  });
});

describe('formatRange', () => {
  it('formats range with both min and max', () => {
    expect(formatRange(5, 30, ' yr')).toBe('5 yr - 30 yr');
    expect(formatRange(1, 10, '%')).toBe('1% - 10%');
  });

  it('returns "-" when both min and max are null', () => {
    expect(formatRange(null, null, '%')).toBe('-');
  });

  it('formats with only min (open upper bound)', () => {
    expect(formatRange(5, null, ' yr')).toBe('5 yr+');
  });

  it('formats with only max (open lower bound)', () => {
    expect(formatRange(null, 30, ' yr')).toBe('up to 30 yr');
  });
});

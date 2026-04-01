import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import RateHeatmap, { type HeatmapBank } from '../RateHeatmap';

function renderWithRouter(banks: readonly HeatmapBank[]) {
  return render(
    <MemoryRouter>
      <RateHeatmap banks={banks} />
    </MemoryRouter>,
  );
}

const makeBanks = (overrides: Partial<HeatmapBank>[] = []): HeatmapBank[] =>
  overrides.map((o, i) => ({
    bank_code: `BANK${i}`,
    bank_name: `Bank ${i}`,
    website_status: 'active',
    rates: {},
    ...o,
  }));

describe('RateHeatmap', () => {
  it('renders bank rows with rate values', () => {
    const banks = makeBanks([
      { bank_name: 'Alpha Bank', rates: { KPR: 7.5, KPA: 9.0 } },
      { bank_name: 'Beta Bank', rates: { KPR: 11.0 } },
    ]);

    renderWithRouter(banks);

    expect(screen.getByText('Alpha Bank')).toBeInTheDocument();
    expect(screen.getByText('Beta Bank')).toBeInTheDocument();
    expect(screen.getByText('7.5%')).toBeInTheDocument();
    expect(screen.getByText('9.0%')).toBeInTheDocument();
    expect(screen.getByText('11.0%')).toBeInTheDocument();
  });

  it('color-codes cells: <8% green, 8-10% yellow, >10% red', () => {
    const banks = makeBanks([
      { rates: { KPR: 5.0, KPA: 9.0, MULTIGUNA: 12.0 } },
    ]);

    renderWithRouter(banks);

    const low = screen.getByText('5.0%');
    expect(low.className).toContain('bg-rate-low');

    const mid = screen.getByText('9.0%');
    expect(mid.className).toContain('bg-rate-mid');

    const high = screen.getByText('12.0%');
    expect(high.className).toContain('bg-rate-high');
  });

  it('shows dash for null/missing rates', () => {
    const banks = makeBanks([{ rates: { KPR: 7.0 } }]);

    renderWithRouter(banks);

    // KPA, MULTIGUNA, KENDARAAN, MODAL_KERJA are missing -> should show "—"
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBe(4);
  });

  it('renders empty state when no banks', () => {
    renderWithRouter([]);

    expect(screen.getByText('No bank data available.')).toBeInTheDocument();
  });
});

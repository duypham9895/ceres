import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SparklineChart from '../SparklineChart';

// Mock recharts ResponsiveContainer since jsdom cannot measure SVG dimensions
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

describe('SparklineChart', () => {
  it('renders with valid data (shows the recharts LineChart)', () => {
    const data = [
      { date: '2025-01-01', value: 10 },
      { date: '2025-01-02', value: 20 },
      { date: '2025-01-03', value: 15 },
    ];

    render(<SparklineChart data={data} />);

    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    expect(screen.queryByText('Insufficient data')).not.toBeInTheDocument();
  });

  it('shows fallback text with insufficient data (< 2 points)', () => {
    render(<SparklineChart data={[{ date: '2025-01-01', value: 10 }]} />);

    expect(screen.getByText('Insufficient data')).toBeInTheDocument();
  });

  it('shows fallback text with empty data', () => {
    render(<SparklineChart data={[]} />);

    expect(screen.getByText('Insufficient data')).toBeInTheDocument();
  });
});

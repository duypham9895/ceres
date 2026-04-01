import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RingChart from '../RingChart';

describe('RingChart', () => {
  const DEFAULT_SIZE = 48;
  const DEFAULT_STROKE = 4;
  const radius = (DEFAULT_SIZE - DEFAULT_STROKE) / 2;
  const circumference = 2 * Math.PI * radius;

  function getForegroundCircle(container: HTMLElement): SVGCircleElement {
    const circles = container.querySelectorAll('circle');
    // The second circle is the foreground (has strokeDasharray)
    return circles[1] as SVGCircleElement;
  }

  it('renders SVG with correct stroke-dasharray at 0%', () => {
    const { container } = render(<RingChart value={0} />);
    const circle = getForegroundCircle(container);

    expect(circle.getAttribute('stroke-dasharray')).toBe(String(circumference));
    expect(circle.getAttribute('stroke-dashoffset')).toBe(String(circumference));
  });

  it('renders SVG with correct stroke-dasharray at 50%', () => {
    const { container } = render(<RingChart value={50} />);
    const circle = getForegroundCircle(container);
    const expectedOffset = circumference - (50 / 100) * circumference;

    expect(circle.getAttribute('stroke-dasharray')).toBe(String(circumference));
    expect(Number(circle.getAttribute('stroke-dashoffset'))).toBeCloseTo(expectedOffset);
  });

  it('renders SVG with correct stroke-dasharray at 100%', () => {
    const { container } = render(<RingChart value={100} />);
    const circle = getForegroundCircle(container);

    expect(circle.getAttribute('stroke-dasharray')).toBe(String(circumference));
    expect(Number(circle.getAttribute('stroke-dashoffset'))).toBeCloseTo(0);
  });
});

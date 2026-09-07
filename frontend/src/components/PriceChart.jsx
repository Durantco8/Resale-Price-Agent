import React, { useState, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  ResponsiveContainer,
} from 'recharts';

import {
  buildChartData,
  formatMoney,
  formatShipping,
  formatTooltipTimestamp,
  formatYAxisPrice,
} from './priceChartUtils';


/**
 * Simple visible dot with click-to-eBay link.
 * Hover detection is handled at the chart container level.
 */
export function ClickableListingDot({ cx, cy, payload, radius = 3 }) {
  if (cx == null || cy == null || !payload) return null;

  const dot = (
    <circle cx={cx} cy={cy} r={radius} className="price-chart__dot" />
  );

  if (!payload.itemUrl) {
    return (
      <g className="price-chart__dot--unavailable" aria-label="Listing link unavailable">
        {dot}
      </g>
    );
  }

  return (
    <a
      href={payload.itemUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${payload.title || 'listing'} on eBay`}
      className="price-chart__dot-link"
    >
      {dot}
    </a>
  );
}


export default function PriceChart({ snapshots }) {
  const [hovered, setHovered] = useState(null);
  const dotPositionsRef = useRef([]);
  const containerRef = useRef(null);

  if (!snapshots || snapshots.length === 0) return null;

  const data = buildChartData(snapshots);
  if (data.length === 0) return null;

  /**
   * Capture each dot's cx/cy/payload during render so we can find
   * the nearest dot on mousemove using Euclidean distance.
   */
  function renderDot(props) {
    const { cx, cy, index, payload } = props;
    if (cx != null && cy != null && payload) {
      dotPositionsRef.current[index] = { cx, cy, payload };
    }
    return <ClickableListingDot {...props} />;
  }

  /**
   * Native mousemove on the container div.  We convert the page
   * coordinates to the SVG coordinate system so we can compare
   * against the stored dot cx/cy values directly.
   */
  function handleMouseMove(e) {
    const container = containerRef.current;
    if (!container) return;

    const svg = container.querySelector('svg');
    if (!svg) return;

    const rect = svg.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const dots = dotPositionsRef.current;
    if (!dots.length) return;

    let nearest = null;
    let minDist = Infinity;
    for (const dot of dots) {
      if (!dot) continue;
      const dx = dot.cx - mouseX;
      const dy = dot.cy - mouseY;
      const dist = dx * dx + dy * dy;
      if (dist < minDist) {
        minDist = dist;
        nearest = dot;
      }
    }

    if (nearest && Math.sqrt(minDist) < 30) {
      setHovered({ point: nearest.payload, cx: nearest.cx, cy: nearest.cy });
    } else {
      setHovered(null);
    }
  }

  function handleMouseLeave() {
    setHovered(null);
  }

  return (
    <div
      className="price-chart"
      style={{ position: 'relative' }}
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <h3>Price History</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
          />
          <YAxis
            tickFormatter={formatYAxisPrice}
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
            width={60}
          />
          <Line
            type="linear"
            dataKey="price"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={renderDot}
            activeDot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      {hovered && (
        <div
          className="price-chart__tooltip"
          style={{
            position: 'absolute',
            left: hovered.cx + 24,
            top: hovered.cy - 40,
            pointerEvents: 'none',
            zIndex: 10,
          }}
        >
          <p className="price-chart__tooltip-title">
            {hovered.point.title || 'Untitled listing'}
          </p>
          <dl className="price-chart__tooltip-details">
            <div>
              <dt>Price</dt>
              <dd>{formatMoney(hovered.point.price, hovered.point.currency)}</dd>
            </div>
            <div>
              <dt>Shipping</dt>
              <dd>{formatShipping(hovered.point.shippingCost, hovered.point.currency)}</dd>
            </div>
            <div>
              <dt>Condition</dt>
              <dd>{hovered.point.condition || 'Unknown condition'}</dd>
            </div>
            <div>
              <dt>Observed</dt>
              <dd>{formatTooltipTimestamp(hovered.point.timestamp)}</dd>
            </div>
          </dl>
          <p className="price-chart__tooltip-link-state">
            {hovered.point.itemUrl ? 'Click point to open listing' : 'Listing link unavailable'}
          </p>
        </div>
      )}
    </div>
  );
}

import React, { useState, useCallback } from 'react';
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


export function ClickableListingDot({ cx, cy, payload, radius = 3, onHover, onLeave }) {
  if (cx == null || cy == null || !payload) return null;

  const visibleDot = (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      className="price-chart__dot"
    />
  );

  // Invisible larger circle for easier hover/click targeting
  const hitArea = (
    <circle
      cx={cx}
      cy={cy}
      r={Math.max(10, radius + 5)}
      className="price-chart__dot-hit-area"
      onMouseEnter={() => onHover && onHover(payload, cx, cy)}
      onMouseLeave={() => onLeave && onLeave()}
    />
  );

  if (!payload.itemUrl) {
    return (
      <g className="price-chart__dot--unavailable" aria-label="Listing link unavailable">
        {hitArea}
        {visibleDot}
      </g>
    );
  }

  const listingName = payload.title || 'listing';
  return (
    <a
      href={payload.itemUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${listingName} on eBay`}
      className="price-chart__dot-link"
    >
      {hitArea}
      {visibleDot}
    </a>
  );
}


export function ListingTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  return (
    <div className="price-chart__tooltip">
      <p className="price-chart__tooltip-title">
        {point.title || 'Untitled listing'}
      </p>
      <dl className="price-chart__tooltip-details">
        <div>
          <dt>Price</dt>
          <dd>{formatMoney(point.price, point.currency)}</dd>
        </div>
        <div>
          <dt>Shipping</dt>
          <dd>{formatShipping(point.shippingCost, point.currency)}</dd>
        </div>
        <div>
          <dt>Condition</dt>
          <dd>{point.condition || 'Unknown condition'}</dd>
        </div>
        <div>
          <dt>Observed</dt>
          <dd>{formatTooltipTimestamp(point.timestamp)}</dd>
        </div>
      </dl>
      <p className="price-chart__tooltip-link-state">
        {point.itemUrl ? 'Click point to open listing' : 'Listing link unavailable'}
      </p>
      {point.itemUrl && (
        <p className="price-chart__tooltip-note">
          Historical listings may no longer be active.
        </p>
      )}
    </div>
  );
}


export default function PriceChart({ snapshots }) {
  const [hovered, setHovered] = useState(null);

  const onDotHover = useCallback((point, cx, cy) => {
    setHovered({ point, cx, cy });
  }, []);

  const onDotLeave = useCallback(() => {
    setHovered(null);
  }, []);

  if (!snapshots || snapshots.length === 0) return null;

  const data = buildChartData(snapshots);
  if (data.length === 0) return null;

  function renderDot(props) {
    return (
      <ClickableListingDot
        {...props}
        onHover={onDotHover}
        onLeave={onDotLeave}
      />
    );
  }

  return (
    <div className="price-chart" style={{ position: 'relative' }}>
      <h3>Price History</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
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
            left: hovered.cx + 12,
            top: hovered.cy - 10,
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

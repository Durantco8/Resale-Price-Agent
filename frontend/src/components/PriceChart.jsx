import React from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Cell,
} from 'recharts';

import {
  buildChartData,
  formatMoney,
  formatShipping,
  formatTooltipTimestamp,
  formatYAxisPrice,
} from './priceChartUtils';


export function ClickableListingDot({ cx, cy, payload, radius = 3 }) {
  if (cx == null || cy == null || !payload) return null;

  const visibleDot = (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      className="price-chart__dot"
    />
  );

  if (!payload.itemUrl) {
    return (
      <g className="price-chart__dot--unavailable" aria-label="Listing link unavailable">
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
      <circle
        cx={cx}
        cy={cy}
        r={Math.max(10, radius + 5)}
        className="price-chart__dot-hit-area"
      />
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


function renderShape(props) {
  const { cx, cy, payload } = props;
  return <ClickableListingDot cx={cx} cy={cy} payload={payload} />;
}


export default function PriceChart({ snapshots }) {
  if (!snapshots || snapshots.length === 0) return null;

  const data = buildChartData(snapshots);
  if (data.length === 0) return null;

  const timestamps = data.map((d) => d.timestamp);
  const spanHours = (Math.max(...timestamps) - Math.min(...timestamps)) / 3600000;

  function formatXTick(ts) {
    const d = new Date(ts);
    if (spanHours < 36) {
      return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    }
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  return (
    <div className="price-chart">
      <h3>Price History</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={formatXTick}
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
            name="Time"
          />
          <YAxis
            dataKey="price"
            type="number"
            tickFormatter={formatYAxisPrice}
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
            width={60}
            name="Price"
          />
          <Tooltip content={<ListingTooltip />} cursor={false} />
          <Scatter data={data} shape={renderShape}>
            {data.map((entry) => (
              <Cell key={entry.snapshotId} fill="var(--color-accent)" />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

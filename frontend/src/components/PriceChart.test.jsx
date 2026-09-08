import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import {
  ClickableListingDot,
} from './PriceChart';
import {
  buildChartData,
  formatDate,
} from './priceChartUtils';


const snapshots = [
  {
    id: 2,
    ebay_item_id: 'v1|222|0',
    title: 'Newer listing',
    price: 190,
    currency: 'USD',
    condition: 'Pre-owned',
    shipping_cost: 0,
    item_url: 'https://www.ebay.com/itm/222',
    snapshot_time: '2026-09-03T21:00:00+00:00',
  },
  {
    id: 1,
    ebay_item_id: 'v1|111|0',
    title: 'Older listing',
    price: 200,
    currency: 'USD',
    condition: 'New',
    shipping_cost: 12.5,
    item_url: 'https://www.ebay.com/itm/111',
    snapshot_time: '2026-09-03T15:00:00+00:00',
  },
];


describe('buildChartData', () => {
  it('reverses newest-first API data and preserves listing metadata', () => {
    const data = buildChartData(snapshots);

    expect(data.map((point) => point.snapshotId)).toEqual([1, 2]);
    expect(data[0]).toMatchObject({
      ebayItemId: 'v1|111|0',
      title: 'Older listing',
      price: 200,
      currency: 'USD',
      condition: 'New',
      shippingCost: 12.5,
      itemUrl: 'https://www.ebay.com/itm/111',
      timestampIso: '2026-09-03T15:00:00+00:00',
    });
    expect(data[0].timestamp).toBe(Date.parse(data[0].timestampIso));
  });
});


describe('smart date axis', () => {
  it('uses time-of-day labels when all data is within 36 hours', () => {
    const data = buildChartData(snapshots);

    expect(data).toHaveLength(2);
    // 6 hours apart — should show time format, not date format
    expect(data[0].date).not.toBe(formatDate(data[0].timestampIso));
    expect(data[0].date).toMatch(/AM|PM/);
    expect(data[1].date).toMatch(/AM|PM/);
  });

  it('uses date labels when data spans multiple days', () => {
    const multiDay = [
      { ...snapshots[0], snapshot_time: '2026-09-10T12:00:00Z' },
      { ...snapshots[1], snapshot_time: '2026-09-03T12:00:00Z' },
    ];
    const data = buildChartData(multiDay);

    expect(data[0].date).toBe(formatDate(data[0].timestampIso));
  });
});


describe('ClickableListingDot', () => {
  it('renders a safe new-tab link for a point with a listing URL', () => {
    const point = buildChartData(snapshots)[0];
    const markup = renderToStaticMarkup(
      <svg><ClickableListingDot cx={20} cy={30} payload={point} /></svg>,
    );

    expect(markup).toContain('href="https://www.ebay.com/itm/111"');
    expect(markup).toContain('target="_blank"');
    expect(markup).toContain('rel="noopener noreferrer"');
    expect(markup).toContain('aria-label="Open Older listing on eBay"');
  });

  it('keeps a missing-URL point visible but non-clickable', () => {
    const point = { ...buildChartData(snapshots)[0], itemUrl: null };
    const markup = renderToStaticMarkup(
      <svg><ClickableListingDot cx={20} cy={30} payload={point} /></svg>,
    );

    expect(markup).not.toContain('<a');
    expect(markup).toContain('price-chart__dot--unavailable');
  });
});



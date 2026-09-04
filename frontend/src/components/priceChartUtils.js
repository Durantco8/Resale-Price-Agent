export function formatMoney(value, currency = 'USD') {
  if (value == null || !Number.isFinite(Number(value))) return 'Unavailable';

  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 2,
    }).format(Number(value));
  } catch {
    return `$${Number(value).toFixed(2)}`;
  }
}


export function formatShipping(value, currency) {
  if (value == null) return 'Shipping unavailable';
  if (Number(value) === 0) return 'Free shipping';
  return `${formatMoney(value, currency)} shipping`;
}


export function formatTooltipTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}


export function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}


export function formatYAxisPrice(value) {
  return `$${Number(value).toFixed(0)}`;
}


export function buildChartData(snapshots) {
  return [...snapshots]
    .reverse()
    .map((snapshot) => ({
      snapshotId: snapshot.id,
      ebayItemId: snapshot.ebay_item_id,
      title: snapshot.title,
      price: snapshot.price,
      currency: snapshot.currency || 'USD',
      condition: snapshot.condition,
      shippingCost: snapshot.shipping_cost,
      itemUrl: snapshot.item_url || null,
      timestampIso: snapshot.snapshot_time,
      timestamp: Date.parse(snapshot.snapshot_time),
      date: formatDate(snapshot.snapshot_time),
    }));
}

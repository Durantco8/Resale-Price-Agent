export default function RecentListings({ snapshots, labels }) {
  if (!snapshots || snapshots.length === 0) return null;

  // Keep only the most recent snapshot per unique ebay_item_id
  const byId = {};
  for (const s of snapshots) {
    if (!s.item_url) continue;
    const existing = byId[s.ebay_item_id];
    if (!existing || s.snapshot_time > existing.snapshot_time) {
      byId[s.ebay_item_id] = s;
    }
  }
  const batch = Object.values(byId)
    .sort((a, b) => a.price - b.price)
    .slice(0, 20);

  if (batch.length === 0) return null;

  // Build a quick lookup from ebay_item_id → label info
  const labelMap = {};
  if (labels) {
    for (const l of labels) {
      labelMap[l.ebay_item_id] = l;
    }
  }

  return (
    <div className="recent-listings">
      <h3>Current Listings</h3>
      <div className="recent-listings__list">
        {batch.map((s) => {
          const labelInfo = labelMap[s.ebay_item_id];
          return (
            <div key={s.id} className="listing-row">
              <div className="listing-row__info">
                <span className="listing-row__price">
                  ${s.price.toFixed(2)}
                </span>
                {labelInfo && (
                  <span className={`listing-label listing-label--${labelClass(labelInfo.label)}`}>
                    {labelInfo.label}
                    <span className="listing-label__pct">
                      {labelInfo.vs_median_pct > 0 ? '+' : ''}{labelInfo.vs_median_pct.toFixed(0)}% vs median
                    </span>
                  </span>
                )}
                <span className="listing-row__detail">
                  {s.condition || 'Unknown condition'}
                </span>
                {s.shipping_cost != null && (
                  <span className="listing-row__detail">
                    {s.shipping_cost === 0
                      ? 'Free shipping'
                      : `$${s.shipping_cost.toFixed(2)} shipping`}
                  </span>
                )}
              </div>
              <a
                href={s.item_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn--secondary listing-row__link"
              >
                View on eBay
              </a>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function labelClass(label) {
  if (label === 'Good Buy') return 'good';
  if (label === 'Overpriced') return 'overpriced';
  return 'fair';
}

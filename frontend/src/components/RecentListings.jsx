export default function RecentListings({ snapshots, labels }) {
  if (!snapshots || snapshots.length === 0) return null;

  // Find the most recent snapshot_time, then grab all listings from that batch
  const latest = snapshots.reduce((a, b) =>
    (a.snapshot_time > b.snapshot_time ? a : b)
  );
  const latestTime = latest.snapshot_time;
  const batch = snapshots
    .filter((s) => s.snapshot_time === latestTime && s.item_url)
    .sort((a, b) => a.price - b.price)
    .slice(0, 10);

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
      <h3>Recent Listings</h3>
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

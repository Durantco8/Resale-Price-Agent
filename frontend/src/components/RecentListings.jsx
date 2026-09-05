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
  const all = Object.values(byId).sort((a, b) => a.price - b.price);
  // Prefer listings with images, fall back to imageless if needed
  const withImages = all.filter((s) => s.image_url);
  const batch = (withImages.length > 0 ? withImages : all).slice(0, 20);

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
      <h3>Recent Listings Tracked (Last 20)</h3>
      <div className="listings-grid">
        {batch.map((s) => {
          const labelInfo = labelMap[s.ebay_item_id];
          return (
            <a
              key={s.id}
              href={s.item_url}
              target="_blank"
              rel="noopener noreferrer"
              className="listing-card"
            >
              <div className="listing-card__image-wrap">
                {s.image_url ? (
                  <img
                    src={s.image_url}
                    alt={s.title || 'Listing'}
                    className="listing-card__image"
                  />
                ) : (
                  <div className="listing-card__placeholder" />
                )}
              </div>
              <div className="listing-card__details">
                <span className="listing-card__price">
                  ${s.price.toFixed(2)}
                </span>
                {labelInfo && (
                  <span className={`listing-label listing-label--${labelClass(labelInfo.label)}`}>
                    {labelInfo.label}
                  </span>
                )}
                <span className="listing-card__condition">
                  {s.condition || 'Unknown'}
                </span>
                {s.shipping_cost != null && (
                  <span className="listing-card__shipping">
                    {s.shipping_cost === 0
                      ? 'Free shipping'
                      : `+$${s.shipping_cost.toFixed(2)}`}
                  </span>
                )}
              </div>
            </a>
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

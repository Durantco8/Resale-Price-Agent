export default function RecentListings({ snapshots }) {
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

  return (
    <div className="recent-listings">
      <h3>Recent Listings</h3>
      <div className="recent-listings__list">
        {batch.map((s) => (
          <div key={s.id} className="listing-row">
            <div className="listing-row__info">
              <span className="listing-row__price">
                ${s.price.toFixed(2)}
              </span>
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
        ))}
      </div>
    </div>
  );
}

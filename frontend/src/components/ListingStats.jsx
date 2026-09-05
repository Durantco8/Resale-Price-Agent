export default function ListingStats({ signals, totalListings }) {
  if (!signals) return null;

  if (!signals.sufficient_data) {
    return (
      <div className="listing-stats listing-stats--collecting">
        <p className="listing-stats__message">Collecting data&hellip; stats will appear after enough poll cycles.</p>
      </div>
    );
  }

  const fmt = (v) => v != null ? `$${v.toFixed(2)}` : '—';

  return (
    <div className="listing-stats">
      <div className="stat-card">
        <span className="stat-card__label">Median</span>
        <span className="stat-card__value">{fmt(signals.latest_batch_median)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">25th Pct</span>
        <span className="stat-card__value stat-card__value--low">{fmt(signals.price_p25)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">75th Pct</span>
        <span className="stat-card__value stat-card__value--high">{fmt(signals.price_p75)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">Listings</span>
        <span className="stat-card__value">{totalListings != null ? totalListings : signals.latest_batch_listing_count}</span>
      </div>
      <div className="stat-card stat-card--secondary">
        <span className="stat-card__label">All-Time Low</span>
        <span className="stat-card__value stat-card__value--low">{fmt(signals.min_price)}</span>
      </div>
      <div className="stat-card stat-card--secondary">
        <span className="stat-card__label">All-Time High</span>
        <span className="stat-card__value stat-card__value--high">{fmt(signals.max_price)}</span>
      </div>
    </div>
  );
}

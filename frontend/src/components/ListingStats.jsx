export default function ListingStats({ snapshots }) {
  if (!snapshots || snapshots.length === 0) return null;

  const prices = snapshots.map((s) => s.price);
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  const min = Math.min(...prices);
  const max = Math.max(...prices);

  return (
    <div className="listing-stats">
      <div className="stat-card">
        <span className="stat-card__label">Average</span>
        <span className="stat-card__value">${avg.toFixed(2)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">Low</span>
        <span className="stat-card__value stat-card__value--low">${min.toFixed(2)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">High</span>
        <span className="stat-card__value stat-card__value--high">${max.toFixed(2)}</span>
      </div>
      <div className="stat-card">
        <span className="stat-card__label">Listings</span>
        <span className="stat-card__value">{snapshots.length}</span>
      </div>
    </div>
  );
}

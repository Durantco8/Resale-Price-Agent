const THRESHOLD = 5;

export default function CollectingState({ snapshotCount }) {
  const progress = Math.min(snapshotCount / THRESHOLD, 1);
  const pct = Math.round(progress * 100);

  return (
    <div className="collecting-state">
      <div className="collecting-state__icon">&#9202;</div>
      <h3>Collecting Data</h3>
      <p>
        We just started tracking this item. Price history and analysis
        will appear once enough data has been collected.
      </p>
      <div className="collecting-state__progress">
        <div className="progress-bar">
          <div className="progress-bar__fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="collecting-state__count">
          {snapshotCount} of {THRESHOLD} data points
        </span>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getTrending } from '../api';

function StatusBadge({ status }) {
  return (
    <span className={`badge badge--${status}`}>
      {status === 'active' ? 'Tracking' : 'Collecting'}
    </span>
  );
}

function actionLabel(decision) {
  if (!decision) return null;
  const labels = { buy_now: 'Buy Now', wait: 'Wait', skip: 'Skip' };
  return labels[decision.action] || decision.action;
}

function actionClass(action) {
  if (action === 'buy_now') return 'action--buy';
  if (action === 'wait') return 'action--wait';
  return 'action--skip';
}

export default function TrendingGrid() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTrending()
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="trending">
        <h2 className="trending__title">Trending Items</h2>
        <div className="trending__loading">Loading trending items...</div>
      </div>
    );
  }

  if (items.length === 0) return null;

  return (
    <div className="trending">
      <h2 className="trending__title">Trending Items</h2>
      <div className="trending__grid">
        {items.map((entry) => {
          const item = entry.tracked_item;
          const dec = entry.recommendation || entry.latest_decision;
          const label = actionLabel(dec);
          const sig = entry.signals_summary;
          return (
            <Link
              key={item.id}
              to={`/item/${item.id}`}
              className="trending-card"
            >
              <div className="trending-card__header">
                <span className="trending-card__name">{item.display_name}</span>
                <StatusBadge status={entry.status} />
              </div>
              <div className="trending-card__meta">
                {sig ? (
                  <span className="trending-card__price">
                    ${sig.latest_batch_median.toFixed(0)}
                  </span>
                ) : (
                  <span className="trending-card__collecting">Collecting data...</span>
                )}
                {label && (
                  <span className={`trending-card__action ${actionClass(dec.action)}`}>
                    {label}
                  </span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

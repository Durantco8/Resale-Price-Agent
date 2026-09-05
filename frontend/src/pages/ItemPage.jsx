import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getItem } from '../api';
import SearchBar from '../components/SearchBar';
import PriceChart from '../components/PriceChart';
import ListingStats from '../components/ListingStats';
import RecentListings from '../components/RecentListings';
import CollectingState from '../components/CollectingState';
import NotifyForm from '../components/NotifyForm';
import ConditionTabs from '../components/ConditionTabs';
import { normalizeCondition } from '../utils/conditions';

export default function ItemPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCondition, setActiveCondition] = useState('All');

  useEffect(() => {
    setLoading(true);
    setError(null);
    setActiveCondition('All');
    getItem(id)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="item-page">
        <SearchBar />
        <div className="item-page__loading">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="item-page">
        <SearchBar />
        <div className="item-page__error">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  const {
    tracked_item, snapshots, status, snapshot_count,
    signals, signals_by_condition, listing_labels,
  } = data;

  // Derive condition tiers present (excluding "All" — that's added by ConditionTabs)
  const conditionTiers = signals_by_condition
    ? Object.keys(signals_by_condition).filter((k) => k !== 'All').sort()
    : [];

  // Filter snapshots by active condition tab
  const filteredSnapshots = activeCondition === 'All'
    ? snapshots
    : snapshots.filter((s) => normalizeCondition(s.condition) === activeCondition);

  // Pick the right signals for the active tab
  const activeSignals = signals_by_condition && signals_by_condition[activeCondition]
    ? signals_by_condition[activeCondition]
    : signals;

  return (
    <div className="item-page">
      <SearchBar />

      <div className="item-page__header">
        {tracked_item.image_url && (
          <img
            src={tracked_item.image_url}
            alt={tracked_item.display_name}
            className="item-page__image"
          />
        )}
        <div>
          <h2 className="item-page__title">{tracked_item.display_name}</h2>
          <span className={`status-badge status-badge--${status}`}>
            {status === 'collecting' ? 'Collecting' : 'Active'}
          </span>
        </div>
      </div>

      {status === 'collecting' ? (
        <CollectingState snapshotCount={snapshot_count} />
      ) : (
        <>
          <ConditionTabs
            conditions={conditionTiers}
            active={activeCondition}
            onChange={setActiveCondition}
          />
          <ListingStats signals={activeSignals} conditionLabel={activeCondition} totalListings={filteredSnapshots.length} />
          <PriceChart snapshots={filteredSnapshots} />
          <RecentListings snapshots={filteredSnapshots} labels={listing_labels} fallbackImage={tracked_item.image_url} />
        </>
      )}

      <NotifyForm trackedItemId={tracked_item.id} />
    </div>
  );
}

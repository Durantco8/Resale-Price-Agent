import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getItem } from '../api';
import SearchBar from '../components/SearchBar';
import PriceChart from '../components/PriceChart';
import ListingStats from '../components/ListingStats';
import RecentListings from '../components/RecentListings';
import RecommendationBanner from '../components/RecommendationBanner';
import CollectingState from '../components/CollectingState';
import NotifyForm from '../components/NotifyForm';

export default function ItemPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
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

  const { tracked_item, snapshots, status, snapshot_count, recommendation, signals } = data;

  return (
    <div className="item-page">
      <SearchBar />

      <h2 className="item-page__title">{tracked_item.display_name}</h2>
      <span className={`status-badge status-badge--${status}`}>
        {status === 'collecting' ? 'Collecting' : 'Active'}
      </span>

      {status === 'collecting' ? (
        <CollectingState snapshotCount={snapshot_count} />
      ) : (
        <>
          <RecommendationBanner recommendation={recommendation} />
          <ListingStats signals={signals} />
          <RecentListings snapshots={snapshots} />
          <PriceChart snapshots={snapshots} />
        </>
      )}

      <NotifyForm trackedItemId={tracked_item.id} />
    </div>
  );
}

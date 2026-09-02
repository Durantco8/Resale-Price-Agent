import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchItem } from '../api';

export default function SearchBar({ large = false }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    try {
      const data = await searchItem(q);
      navigate(`/item/${data.tracked_item.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={`search-bar ${large ? 'search-bar--large' : ''}`}>
      <div className="search-bar__input-wrap">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='Search any item (e.g. "Jordan 4 Retro Military Black")'
          disabled={loading}
          autoFocus={large}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      {error && <p className="search-bar__error">{error}</p>}
    </form>
  );
}

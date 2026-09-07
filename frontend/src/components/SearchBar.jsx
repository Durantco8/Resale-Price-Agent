import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { suggestItems, requestCard } from '../api';

export default function SearchBar({ large = false }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [results, setResults] = useState(null); // null = no search yet, [] = no matches
  const [activeIndex, setActiveIndex] = useState(-1);
  const navigate = useNavigate();
  const wrapRef = useRef(null);
  const debounceRef = useRef(null);

  // Fetch suggestions as user types (debounced)
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const items = await suggestItems(q);
        setSuggestions(items);
        // Only show dropdown if we haven't submitted a search yet
        if (items.length > 0) setShowDropdown(true);
        setActiveIndex(-1);
      } catch {
        setSuggestions([]);
        setShowDropdown(false);
      }
    }, 250);

    return () => clearTimeout(debounceRef.current);
  }, [query]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function selectItem(item) {
    setQuery('');
    setSuggestions([]);
    setShowDropdown(false);
    setResults(null);
    navigate(`/item/${item.id}`);
  }

  function handleKeyDown(e) {
    if (!showDropdown || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      selectItem(suggestions[activeIndex]);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    // Fetch and show all results below
    setShowDropdown(false);
    try {
      const items = await suggestItems(q);
      setResults(items);
    } catch {
      setResults([]);
    }
  }

  function handleInputChange(e) {
    setQuery(e.target.value);
    setResults(null); // Clear search results when typing again
  }

  return (
    <div className={`search-bar ${large ? 'search-bar--large' : ''}`} ref={wrapRef}>
      <form onSubmit={handleSubmit}>
        <div className="search-bar__input-wrap">
          <input
            type="text"
            value={query}
            onChange={handleInputChange}
            onFocus={() => suggestions.length > 0 && !results && setShowDropdown(true)}
            onKeyDown={handleKeyDown}
            placeholder='Search tracked items (e.g. "Charizard Base Set")'
            autoFocus={large}
            autoComplete="off"
          />
          <button type="submit" disabled={!query.trim()}>
            Search
          </button>
        </div>
      </form>

      {showDropdown && !results && (
        <ul className="search-bar__dropdown">
          {suggestions.map((item, i) => (
            <li
              key={item.id}
              className={`search-bar__suggestion ${i === activeIndex ? 'search-bar__suggestion--active' : ''}`}
              onMouseDown={() => selectItem(item)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {item.image_url && (
                <img
                  src={item.image_url}
                  alt=""
                  className="search-bar__suggestion-img"
                />
              )}
              <span className="search-bar__suggestion-name">{item.display_name}</span>
            </li>
          ))}
        </ul>
      )}

      {results !== null && results.length > 0 && (
        <div className="search-results">
          <h3 className="search-results__heading">
            {results.length} result{results.length !== 1 ? 's' : ''} for &ldquo;{query}&rdquo;
          </h3>
          <div className="search-results__grid">
            {results.map((item) => (
              <button
                key={item.id}
                className="search-results__card"
                onClick={() => selectItem(item)}
              >
                {item.image_url ? (
                  <img src={item.image_url} alt="" className="search-results__card-img" />
                ) : (
                  <div className="search-results__card-placeholder" />
                )}
                <span className="search-results__card-name">{item.display_name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {results !== null && results.length === 0 && (
        <NoResultsCard query={query} />
      )}
    </div>
  );
}


function NoResultsCard({ query }) {
  const [requestStatus, setRequestStatus] = useState('idle'); // idle | form | sending | sent | error
  const [cardName, setCardName] = useState(query);
  const [details, setDetails] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    const name = cardName.trim();
    if (!name) return;

    const message = details.trim()
      ? `${name}\n\nDetails: ${details.trim()}`
      : name;

    setRequestStatus('sending');
    try {
      await requestCard(message);
      setRequestStatus('sent');
    } catch {
      setRequestStatus('error');
    }
  }

  return (
    <div className="no-results">
      <div className="no-results__icon">&#128269;</div>
      <h3 className="no-results__title">No results found</h3>
      <p className="no-results__message">
        &ldquo;{query}&rdquo; isn&rsquo;t currently being tracked.
      </p>

      {requestStatus === 'sent' ? (
        <div className="no-results__success">
          <span className="no-results__check">&#10003;</span>
          <p>Request submitted! We&rsquo;ll review and may add this card soon.</p>
        </div>
      ) : requestStatus === 'form' || requestStatus === 'sending' || requestStatus === 'error' ? (
        <form onSubmit={handleSubmit} className="no-results__form">
          <label className="no-results__label">
            Full card name *
            <input
              type="text"
              value={cardName}
              onChange={(e) => setCardName(e.target.value)}
              placeholder='e.g. "Charizard 4/102 Base Set Holo PSA 9"'
              className="no-results__input"
              required
            />
          </label>
          <label className="no-results__label">
            Additional details
            <textarea
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder="Set name, card number, condition, grading, language, etc."
              className="no-results__textarea"
              rows={3}
            />
          </label>
          <button
            type="submit"
            className="no-results__request-btn"
            disabled={requestStatus === 'sending' || !cardName.trim()}
          >
            {requestStatus === 'sending' ? 'Submitting...' : 'Submit Request'}
          </button>
          {requestStatus === 'error' && (
            <p className="no-results__error">
              Something went wrong. Please try again.
            </p>
          )}
        </form>
      ) : (
        <>
          <p className="no-results__cta">
            Want us to track this card? Fill out a quick request and we&rsquo;ll review it.
          </p>
          <button
            className="no-results__request-btn"
            onClick={() => setRequestStatus('form')}
          >
            Request Tracking
          </button>
        </>
      )}
    </div>
  );
}

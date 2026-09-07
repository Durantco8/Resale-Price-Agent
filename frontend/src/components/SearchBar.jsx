import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { suggestItems } from '../api';

export default function SearchBar({ large = false }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
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
        const results = await suggestItems(q);
        setSuggestions(results);
        setShowDropdown(results.length > 0);
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

  function handleSubmit(e) {
    e.preventDefault();
    // If there are suggestions and user hits Enter without selecting, go to first result
    if (suggestions.length > 0) {
      selectItem(suggestions[0]);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={`search-bar ${large ? 'search-bar--large' : ''}`}
      ref={wrapRef}
    >
      <div className="search-bar__input-wrap">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
          onKeyDown={handleKeyDown}
          placeholder='Search tracked items (e.g. "Charizard Base Set")'
          autoFocus={large}
          autoComplete="off"
        />
        <button type="submit" disabled={!query.trim()}>
          Search
        </button>
      </div>

      {showDropdown && (
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
    </form>
  );
}

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

export function searchItem(query) {
  return request(`/api/search?q=${encodeURIComponent(query)}`);
}

export function suggestItems(query) {
  return request(`/api/suggest?q=${encodeURIComponent(query)}`);
}

export function getItem(id) {
  return request(`/api/items/${id}`);
}

export function getTrending() {
  return request('/api/trending');
}

export function createAlert({ email, tracked_item_id, condition }) {
  return request('/api/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, tracked_item_id, condition }),
  });
}

export function requestCard(cardName) {
  return request('/api/request-card', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_name: cardName }),
  });
}

export function unsubscribe(token) {
  return request(`/api/unsubscribe/${token}`);
}

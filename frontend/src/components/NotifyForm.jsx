import { useState } from 'react';
import { createAlert } from '../api';

export default function NotifyForm({ trackedItemId }) {
  const [email, setEmail] = useState('');
  const [conditionType, setConditionType] = useState('buy_now');
  const [priceThreshold, setPriceThreshold] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    const condition =
      conditionType === 'price_below'
        ? `price_below:${parseFloat(priceThreshold).toFixed(2)}`
        : 'buy_now';

    if (conditionType === 'price_below' && (!priceThreshold || isNaN(priceThreshold))) {
      setError('Enter a valid price threshold.');
      return;
    }

    setLoading(true);
    try {
      await createAlert({ email, tracked_item_id: trackedItemId, condition });
      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="notify-form notify-form--success">
        <div className="notify-form__icon">&#10003;</div>
        <p>Alert created! We'll email <strong>{email}</strong> when your condition is met.</p>
        <button onClick={() => { setSuccess(false); setEmail(''); }} className="btn btn--secondary">
          Set another alert
        </button>
      </div>
    );
  }

  return (
    <div className="notify-form">
      <h3>Get Notified</h3>
      <form onSubmit={handleSubmit}>
        <div className="notify-form__field">
          <label htmlFor="notify-email">Email</label>
          <input
            id="notify-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>
        <div className="notify-form__field">
          <label htmlFor="notify-condition">Alert when</label>
          <select
            id="notify-condition"
            value={conditionType}
            onChange={(e) => setConditionType(e.target.value)}
          >
            <option value="buy_now">AI recommends "Buy Now"</option>
            <option value="price_below">Price drops below...</option>
          </select>
        </div>
        {conditionType === 'price_below' && (
          <div className="notify-form__field">
            <label htmlFor="notify-price">Price threshold ($)</label>
            <input
              id="notify-price"
              type="number"
              min="0"
              step="0.01"
              value={priceThreshold}
              onChange={(e) => setPriceThreshold(e.target.value)}
              placeholder="180.00"
              required
            />
          </div>
        )}
        {error && <p className="notify-form__error">{error}</p>}
        <button type="submit" className="btn btn--primary" disabled={loading}>
          {loading ? 'Creating...' : 'Create Alert'}
        </button>
      </form>
    </div>
  );
}

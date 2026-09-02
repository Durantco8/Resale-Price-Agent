import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { unsubscribe } from '../api';

export default function UnsubscribePage() {
  const { token } = useParams();
  const [status, setStatus] = useState('loading'); // loading | success | error
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    unsubscribe(token)
      .then(() => setStatus('success'))
      .catch((err) => {
        setErrorMsg(err.message);
        setStatus('error');
      });
  }, [token]);

  return (
    <div className="unsubscribe-page">
      {status === 'loading' && (
        <div className="unsubscribe-page__card">
          <p>Processing your request...</p>
        </div>
      )}
      {status === 'success' && (
        <div className="unsubscribe-page__card unsubscribe-page__card--success">
          <div className="unsubscribe-page__icon">&#10003;</div>
          <h2>Unsubscribed</h2>
          <p>You've been removed from this alert. No further emails will be sent.</p>
          <Link to="/" className="btn btn--primary">Back to Home</Link>
        </div>
      )}
      {status === 'error' && (
        <div className="unsubscribe-page__card unsubscribe-page__card--error">
          <h2>Something went wrong</h2>
          <p>{errorMsg}</p>
          <Link to="/" className="btn btn--secondary">Back to Home</Link>
        </div>
      )}
    </div>
  );
}

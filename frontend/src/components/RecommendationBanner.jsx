function actionClass(action) {
  if (action === 'buy_now') return 'action--buy';
  if (action === 'wait') return 'action--wait';
  return 'action--skip';
}

function formatAction(action) {
  const labels = { buy_now: 'Buy Now', wait: 'Wait', skip: 'Skip' };
  return labels[action] || action;
}

export default function RecommendationBanner({ recommendation }) {
  if (!recommendation) return null;

  const confidencePct = recommendation.confidence != null
    ? `${(recommendation.confidence * 100).toFixed(0)}%`
    : null;

  return (
    <div className={`rec-banner ${actionClass(recommendation.action)}`}>
      <div className="rec-banner__header">
        <span className="rec-banner__label">Recommendation</span>
        <span className="rec-banner__action">{formatAction(recommendation.action)}</span>
        {confidencePct && (
          <span className="rec-banner__confidence">{confidencePct} confidence</span>
        )}
      </div>
      <p className="rec-banner__reasoning">{recommendation.reasoning}</p>
    </div>
  );
}

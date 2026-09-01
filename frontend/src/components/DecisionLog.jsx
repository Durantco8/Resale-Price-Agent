function actionClass(action) {
  if (action === 'buy_now') return 'decision--buy';
  if (action === 'wait') return 'decision--wait';
  return 'decision--skip';
}

function formatAction(action) {
  const labels = { buy_now: 'Buy Now', wait: 'Wait', skip: 'Skip' };
  return labels[action] || action;
}

function formatTime(iso) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function DecisionLog({ decisions }) {
  if (!decisions || decisions.length === 0) return null;

  // Only show LLM reasoning decisions
  const llmDecisions = decisions.filter((d) => d.event_type === 'llm_reasoning');
  if (llmDecisions.length === 0) return null;

  return (
    <div className="decision-log">
      <h3>Analysis Log</h3>
      <div className="decision-log__list">
        {llmDecisions.slice(0, 10).map((d) => (
          <div key={d.id} className={`decision-entry ${actionClass(d.action)}`}>
            <div className="decision-entry__header">
              <span className="decision-entry__action">{formatAction(d.action)}</span>
              <span className="decision-entry__confidence">
                {d.confidence != null ? `${(d.confidence * 100).toFixed(0)}% confidence` : ''}
              </span>
              <span className="decision-entry__time">{formatTime(d.timestamp)}</span>
            </div>
            <p className="decision-entry__reasoning">{d.reasoning}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ConditionTabs({ conditions, active, onChange }) {
  // Hide tabs if only "All" or just one condition tier
  if (!conditions || conditions.length <= 1) return null;

  const tabs = ['All', ...conditions];

  return (
    <div className="condition-tabs">
      {tabs.map((cond) => (
        <button
          key={cond}
          className={`condition-tabs__tab${cond === active ? ' condition-tabs__tab--active' : ''}`}
          onClick={() => onChange(cond)}
        >
          {cond}
        </button>
      ))}
    </div>
  );
}

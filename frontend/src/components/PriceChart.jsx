import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatPrice(val) {
  return `$${Number(val).toFixed(0)}`;
}

export default function PriceChart({ snapshots }) {
  if (!snapshots || snapshots.length === 0) return null;

  // Snapshots come newest-first from the API; reverse for chronological
  const data = [...snapshots]
    .reverse()
    .map((s) => ({
      date: formatDate(s.snapshot_time),
      price: s.price,
      title: s.title,
    }));

  return (
    <div className="price-chart">
      <h3>Price History</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
          />
          <YAxis
            tickFormatter={formatPrice}
            tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
            width={60}
          />
          <Tooltip
            formatter={(val) => [`$${Number(val).toFixed(2)}`, 'Price']}
            contentStyle={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
            }}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={{ r: 3, fill: 'var(--color-accent)' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

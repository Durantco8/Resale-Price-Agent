import { Link } from 'react-router-dom';

export default function Layout({ children }) {
  return (
    <div className="app-layout">
      <header className="app-header">
        <Link to="/" className="logo-link">
          <span className="logo-icon">&#9650;</span>
          <span className="logo-text">PokéTracker</span>
        </Link>
      </header>
      <main className="app-main">{children}</main>
      <footer className="app-footer">
        <p>Real-time Pokemon card price tracking and buy/wait/skip recommendations.</p>
      </footer>
    </div>
  );
}

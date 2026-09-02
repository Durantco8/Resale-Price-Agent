import SearchBar from '../components/SearchBar';
import TrendingGrid from '../components/TrendingGrid';

export default function HomePage() {
  return (
    <div className="home-page">
      <section className="hero-section">
        <h1 className="hero-section__title">
          Track resale prices.<br />
          <span className="hero-section__subtitle">Know when to buy.</span>
        </h1>
        <p className="hero-section__desc">
          Search any item to see its eBay price history, trend analysis,
          and AI-powered buy/wait/skip recommendations — no account needed.
        </p>
        <SearchBar large />
      </section>
      <TrendingGrid />
    </div>
  );
}

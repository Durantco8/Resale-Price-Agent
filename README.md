# PokéTracker

**Track Pokemon card prices. Know when to buy.**

[**Visit the live site →**](https://resale-price-agent.vercel.app)

---

## What is PokéTracker?

PokéTracker is a Pokemon card price tracking tool that collects real-time eBay listing data, analyzes price trends, and helps collectors make smarter buying decisions. It tracks 80 curated Pokemon cards — from vintage Base Set holos to modern alt arts — and updates daily with fresh market data.

---

## Features

- **Price History Charts** — Interactive graphs showing price trends over time for every tracked card. Click any data point to view the original eBay listing.
- **Condition-Segmented Stats** — Separate price analytics for Graded vs. Raw cards, so you're comparing apples to apples.
- **Per-Listing Labels** — Each listing is tagged as Good Buy, Fair Price, or Overpriced based on the current market median for its condition tier.
- **Autocomplete Search** — Start typing a card name and instantly see matching results with thumbnail previews.
- **Card Request System** — Don't see a card you want tracked? Submit a request with the card details and it'll be reviewed.
- **Thumbnail Images** — Card images on the homepage grid and per-listing eBay thumbnails on detail pages.
- **Daily eBay Polling** — Automated data collection runs every day, building deeper trend history over time.
- **Outlier Detection** — Accessory listings and mismatched results are automatically filtered out so price stats stay accurate.

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| Python 3.12 | Core application language |
| Flask | REST API framework |
| SQLAlchemy | Database ORM (Core, not ORM mode) |
| PostgreSQL | Production database (Render free tier) |
| Gunicorn | Production WSGI server |

### Frontend
| Technology | Purpose |
|---|---|
| React 19 | UI framework |
| React Router | Client-side routing |
| Recharts | Price history chart visualizations |
| Vite | Build tool and dev server |

### External APIs
| Service | Purpose |
|---|---|
| eBay Browse API | Real-time listing data and pricing |
| Google Gemini | Optional extended market analysis |
| Gmail SMTP | Email notifications and card requests |

### Infrastructure
| Service | Purpose |
|---|---|
| Render | Backend hosting, cron jobs, PostgreSQL |
| Vercel | Frontend hosting |

---

## How It Works

```
eBay Browse API  →  Daily Poller  →  PostgreSQL
                                         ↓
                              Statistical Signals
                          (median, trend, percentiles)
                                         ↓
                           Deterministic Engine
                            (BUY / WAIT / SKIP)
                                         ↓
                              Flask REST API
                                         ↓
                             React Frontend
```

1. **Poll** — A daily cron job queries the eBay Browse API for each tracked card, filtering by category to avoid accessories and mismatches.
2. **Store** — New listings are deduplicated and stored as snapshots. Outliers (suspiciously cheap accessories) are filtered using median-based detection.
3. **Analyze** — Longitudinal signals are computed across poll batches: price trends, supply trends, percentiles, and batch-over-batch comparisons.
4. **Recommend** — A deterministic rules engine evaluates signals to produce BUY, WAIT, or SKIP recommendations with confidence scores.
5. **Display** — The React frontend presents price charts, stats, per-listing labels, and search/discovery tools.

---

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 18+
- eBay Developer Account ([developer.ebay.com](https://developer.ebay.com))

### Backend Setup

```bash
# Clone the repo
git clone https://github.com/Durantco8/Resale-Price-Agent.git
cd Resale-Price-Agent

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your eBay API keys and other config

# Start the Flask API
flask --app resale_price_agent.app run --port 5001
```

### Frontend Setup

```bash
cd frontend
npm install

# Set API URL (points to local backend)
echo 'VITE_API_URL=http://localhost:5001' > .env

npm run dev
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (or omit for SQLite) |
| `EBAY_CLIENT_ID` | Yes | eBay Developer app ID |
| `EBAY_CLIENT_SECRET` | Yes | eBay Developer app secret |
| `GEMINI_API_KEY` | No | Google Gemini API key for optional analysis |
| `NOTIFY_TO` | No | Email address for notifications and card requests |
| `SMTP_HOST` | No | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SMTP_USER` | No | SMTP login email |
| `SMTP_PASSWORD` | No | SMTP app password |
| `POLLER_OWNER` | No | Owner identifier for personal item tracking |

---

## Testing

```bash
# Backend tests (365 tests)
.venv/bin/pytest

# Frontend tests (5 tests)
cd frontend && npx vitest run
```

Test coverage includes: database operations, eBay API client, recommendation engine (44 scenario tests), signal computation, alert matching, outlier detection, price/listing trends, and API endpoints.

---

## Project Structure

```
├── resale_price_agent/       # Backend Python package
│   ├── app.py                # Flask API routes
│   ├── db.py                 # Database schema and queries
│   ├── ebay_client.py        # eBay Browse API client
│   ├── poller.py             # Polling pipeline (fetch → store → analyze)
│   ├── recommendation.py     # Deterministic BUY/WAIT/SKIP engine
│   ├── signals.py            # Statistical signal computation
│   ├── conditions.py         # Condition normalization and listing labels
│   ├── notifier.py           # Email notification sender
│   └── seed_list.py          # 80 curated Pokemon card definitions
├── frontend/                 # React frontend (Vite)
│   └── src/
│       ├── components/       # SearchBar, PriceChart, TrendingGrid, etc.
│       ├── pages/            # HomePage, ItemPage
│       └── api.js            # API client
├── tests/                    # 365 backend tests
├── poller.py                 # CLI entry point for the polling pipeline
├── render.yaml               # Render deployment config
└── requirements.txt          # Python dependencies
```

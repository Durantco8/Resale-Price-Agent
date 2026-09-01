# Resale Price Agent — Project Spec

## Purpose

An agent that tracks **multiple user-provided items** on eBay at once,
polling live listings for each one, and notifies me when a low-price drop
occurs — either a new listing appearing meaningfully below the item's recent
average, or the agent's own trend reasoning concluding conditions look like
a good time to buy. Every notification-worthy event and every reasoning
decision gets logged, so results can later be evaluated against what prices
actually did.

This is a **decision-support / watchlist agent, not an auto-purchasing
bot**. It never executes a purchase. Its job ends at detecting a good price
and sending a notification. No scraping — all data comes from eBay's
official Browse API.

There are two complementary detection paths, and both matter:

1. **Deterministic price-drop alerts** (fast, cheap, no LLM) — compare each
   new snapshot against the item's own recent history; if a new listing
   appears meaningfully below the rolling average or below a user-set target
   price, alert immediately. This should never depend on the LLM being
   available or correct — it's a plain threshold/statistics check.
2. **LLM trend reasoning** (slower, adds judgment) — once there's enough
   history for an item, ask the LLM to reason over the computed signals
   (trend direction, volatility, listing volume) and decide
   `buy_now` / `wait` / `skip` with a reasoning string. This is a second,
   softer signal layered on top of #1, not a replacement for it.

The end goal is a working pipeline, across multiple tracked items at once,
with a backtest: after a few weeks of logged data, compare what the agent
flagged/recommended against what actually happened to each item's price.

## Why this project exists (context for design decisions)

This is a portfolio/learning project modeled after an earlier project of mine
(a Python/Flask seat availability tracker with a scraper, SQLAlchemy/SQLite
storage, retry-safe notifications, and pytest coverage using dependency
injection to mock external services). Reuse that same architectural
philosophy here:
- deterministic logic (data fetching, math) stays in plain Python — the LLM
  is only used for the reasoning/decision step, never for computing numbers
- external services (eBay API, LLM API, email) should be mockable via
  dependency injection so the full pipeline can be tested without hitting
  live services
- favor a system that's honest about failure — if the eBay API is down or a
  poll fails, the system should log that clearly, not silently skip or crash

## Tech stack

- **Language:** Python
- **Data storage:** SQLite via SQLAlchemy Core (same pattern as the seat
  tracker — prefer explicit atomic transactions over ORM magic)
- **External API:** eBay Browse API (`item_summary/search` endpoint),
  client-credentials OAuth flow
- **LLM:** Anthropic API (Claude) or OpenAI API — structured/JSON output for
  the decision step, not free-text
- **Notifications:** SMTP email (reuse the seat tracker's email pattern if
  useful)
- **Testing:** pytest, with dependency injection to fake the eBay client and
  LLM client so tests run in milliseconds with no network calls
- **Scheduling:** simple polling loop or APScheduler — runs on an interval
  (e.g. every few hours), not real-time

## Build order (please build in this order, confirming each stage works
before moving to the next)

### Stage 1 — eBay API client
- OAuth client-credentials token fetch, with caching and refresh before
  expiry (tokens last ~2 hours)
- A `search_listings(query, limit)` function wrapping
  `GET /buy/browse/v1/item_summary/search`
- Return the fields we actually need: item id, title, price, condition,
  seller feedback score, item URL, listing snapshot time
- Write this so it's easily mockable in tests (inject the token-fetcher and
  HTTP client, don't hardcode `requests.get` calls directly inside business
  logic)

### Stage 2 — Storage layer
- A `tracked_items` table: id, search query, an optional user-set target
  price, active/paused flag, date added. This is what makes tracking
  multiple items possible — the poller iterates this table rather than
  polling one hardcoded query.
- A `listing_snapshots` table: tracked_item_id (FK), ebay item id, price,
  condition, seller feedback, shipping cost, item location, format
  (auction/fixed price), timestamp
- A `decisions` table logging every agent event per tracked item: timestamp,
  tracked_item_id, event type (`price_drop_alert` or `llm_reasoning`),
  computed signals, action/confidence/reasoning (nullable for the
  deterministic path, which doesn't need an LLM reasoning string — a plain
  "X% below average" note is enough), and a nullable `outcome` field for
  later backtesting
- Simple insert/query functions, atomic writes

### Stage 3 — Item management
- A small interface for adding/removing/pausing tracked items — a CLI is
  enough for now (e.g. `python manage_items.py add "Jordan 4 Retro Military
  Black size 10" --target-price 150`), no web UI needed yet
- This is what "give it items and it tracks them" actually means in code —
  get this right before building the polling loop on top of it

### Stage 4 — Polling script
- On each run: loop over all active rows in `tracked_items`, call the eBay
  client for each one's query, store a snapshot row per listing, and log
  clearly what happened per item (including failures — one item's API
  error shouldn't stop the others from being polled)

### Stage 5 — Deterministic price-drop detection
- After storing new snapshots for an item, compare against that item's own
  recent history: flag if a new listing is meaningfully below the rolling
  average (e.g. more than some % below), or below the user's target price
  if one is set
- This must work correctly with zero LLM involvement and zero network calls
  beyond eBay — it's the fast, reliable core of "notify me when a low price
  drops"
- Handle the cold-start case (not enough history yet) gracefully

### Stage 6 — Signal computation (for the LLM layer)
- Once there's enough history for an item, compute: rolling average price,
  min/max over the window, day-over-day trend, listing count trend
- Keep this pure Python/math — no LLM involvement here either

### Stage 7 — LLM decision layer
- Take the computed signals for an item + a short summary of its current
  listings and send them to the LLM with a system prompt that asks for a
  **structured JSON response only**: `{ action: "buy_now" | "wait" |
  "skip", confidence: 0-1, reasoning: string }`
- Validate/parse the JSON response defensively — the pipeline should not
  crash if the LLM returns something malformed; log and skip that item's
  reasoning cycle instead, without affecting other tracked items
- Store the decision in the `decisions` table

### Stage 8 — Notification
- Send an email when either detection path fires: a deterministic
  price-drop alert, or an LLM `buy_now` decision (with its reasoning
  attached)
- Each tracked item's notifications should be clearly distinguishable in
  the email (which item, what triggered it, what the price is)
- Reuse the retry-safe notification pattern from the seat tracker project
  if that code is available to reference — don't let a failed email crash
  the pipeline or block other items from being processed

### Stage 9 — Tests
- pytest suite with dependency injection faking the eBay client, LLM client,
  and email sender
- Cover: normal flow across multiple tracked items, one item's eBay API
  failure not affecting others, malformed LLM response, cold-start with
  insufficient data, deterministic alert firing correctly at threshold
  boundaries, notification failure

### Stage 10 (later, not urgent) — Backtest tooling
- A script that, given decisions logged over time and later-observed prices,
  fills in the `outcome` field and reports how often alerts/`buy_now` calls
  were actually followed by good outcomes (i.e., was the agent right)
- This stage can wait until there's a few weeks of real logged data

### Stage 11 (later, not urgent) — Dashboard
- A small Flask dashboard (same pattern as the seat tracker) showing
  tracked items, their price history, and the log of past
  alerts/decisions with reasoning
- Only worth building once Stages 1–9 are solid and producing real data

## What NOT to build right now

- No automatic purchasing — decision-support only
- No web dashboard yet — CLI/logs/email are enough for the first version
- No multi-source aggregation yet (Etsy, Best Buy, etc.) — eBay only for
  the first working version
- No image-based search or anything beyond the Browse API's keyword search
  for now
- No user accounts / multi-user support — this is a personal tool tracking
  items for one person (me), even though it tracks multiple items at once

## Current status

- eBay Developer account registered, pending approval (~1 business day)
- No code written yet — this is a fresh build

## Questions to ask me before/while building, if anything is ambiguous

- Exact items to track first (I'll provide once we start)
- Whether to use Anthropic or OpenAI for the LLM decision step
- Polling interval (suggest starting with every few hours, adjustable, same
  for all tracked items to start — per-item intervals are a later nice-to-have)
- What "meaningfully below average" means as a default threshold for the
  deterministic alert (e.g. 10-15% below rolling average) if I don't set a
  target price for an item
- Notification thresholds (confidence cutoff for LLM-triggered alerts)

# Resale Price Agent — Project Spec

## Purpose

An agent that monitors live eBay listings for a specific resale item (starting
with sneakers, e.g. "Jordan 4 Retro Military Black size 10"), computes pricing
signals from the data it collects over time, and uses an LLM to decide
whether the current market is a "buy now," "wait," or "skip" — logging every
decision along with its reasoning so the decisions can later be evaluated
against what the price actually did.

This is a **decision-support agent, not an auto-purchasing bot**. It never
executes a purchase. Its job ends at producing a reasoned recommendation and
sending a notification. No scraping — all data comes from eBay's official
Browse API.

The end goal is a working pipeline with a backtest: after a few weeks of
logged decisions, compare what the agent recommended against what actually
happened to the price, so the project has real evidence of whether its
reasoning was any good — not just that it runs.

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
- SQLite schema with a `listing_snapshots` table: item id, query, price,
  condition, seller feedback, timestamp, and whatever else is useful
- A `decisions` table logging every agent decision: timestamp, query,
  computed signals (avg price, trend, etc.), the LLM's action/confidence/
  reasoning, and (nullable, filled in later) an `outcome` field for backtesting
- Simple insert/query functions, atomic writes

### Stage 3 — Polling script
- On each run: call the eBay client for the configured query/queries, store
  a snapshot row per listing (or an aggregated summary row — your call on
  the cleanest schema), and log clearly what happened

### Stage 4 — Signal computation
- Once there are multiple snapshots for a query, compute: rolling average
  price, min/max over the window, day-over-day trend, listing count trend
- Keep this pure Python/math — no LLM involvement here
- Handle the cold-start case gracefully (not enough data yet to compute a
  trend) rather than crashing

### Stage 5 — LLM decision layer
- Take the computed signals + a short summary of current listings and send
  them to the LLM with a system prompt that asks for a **structured JSON
  response only**: `{ action: "buy_now" | "wait" | "skip", confidence: 0-1,
  reasoning: string }`
- Validate/parse the JSON response defensively — the pipeline should not
  crash if the LLM returns something malformed; log and skip that cycle
  instead
- Store the decision in the `decisions` table

### Stage 6 — Notification
- If `action == "buy_now"` (or confidence crosses some threshold), send an
  email with the reasoning attached
- Reuse the retry-safe notification pattern from the seat tracker project
  if that code is available to reference — don't let a failed email crash
  the pipeline

### Stage 7 — Tests
- pytest suite with dependency injection faking the eBay client, LLM client,
  and email sender
- Cover: normal flow, eBay API failure, malformed LLM response, cold-start
  with insufficient data, notification failure

### Stage 8 (later, not urgent) — Backtest tooling
- A script that, given decisions logged over time and later-observed prices,
  fills in the `outcome` field and reports how often "buy_now" calls were
  actually followed by price increases (i.e., was the agent right)
- This stage can wait until there's a few weeks of real logged data

## What NOT to build right now

- No automatic purchasing — decision-support only
- No web dashboard yet (can add later, following the seat tracker's Flask
  dashboard pattern if wanted)
- No multi-source aggregation yet (Etsy, Best Buy, etc.) — eBay only for
  the first working version
- No image-based search or anything beyond the Browse API's keyword search
  for now

## Current status

- eBay Developer account registered, pending approval (~1 business day)
- No code written yet — this is a fresh build

## Questions to ask me before/while building, if anything is ambiguous

- Exact sneaker model/size to track first (I'll provide once we start)
- Whether to use Anthropic or OpenAI for the LLM decision step
- Polling interval (suggest starting with every few hours, adjustable)
- Notification thresholds (confidence cutoff for sending an alert)

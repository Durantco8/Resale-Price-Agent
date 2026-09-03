# Resale Price Agent — Progress Summary

*Last updated: Sep 3, 2026 (Session 5, Phase 1 complete). This file replaces all earlier progress-summary docs — treat this as the single source of truth. Have Claude Code or Codex read it first when starting a new session.*

**Project path:** `/Users/durantco/Documents/RESUME PROJECTS/Resale Price Agent`
**GitHub:** `Durantco8/Resale-Price-Agent`
**Stack:** Python CLI pipeline + Flask backend + React (Vite) frontend + **SQLite (confirmed — see Section 8, this is NOT Postgres despite earlier assumptions)**
**Purpose:** Started as a personal eBay resale price-tracking agent, evolved into a public-facing site where any user can search an item, view price trends, and (eventually) sign up for email alerts.

---

## 1. Origins

- Began as a personal CLI tool: poll eBay Browse API for a specific item (e.g. "Jordan 4 Retro Military Black size 10"), store price snapshots over time, compute rolling signals, and use an LLM (Gemini) to reason about buy/wait/skip decisions.
- Later expanded into a public web platform: Flask REST API + React frontend, allowing any visitor to search an item and see its tracked price history/trends, not just the one item CD personally tracks.
- This dual-purpose nature (personal tool + public product) is the source of most design challenges tackled so far — see Section 3.

---

## 2. eBay API Setup

- Registered for eBay Developer Program access; approval took about a day.
- Hit `invalid_client` OAuth errors initially even with correct Production keys — turned out to be a normal propagation delay eBay has after keyset creation, not a config issue. Resolved after waiting.
- Auth flow: client credentials grant (`api.ebay.com/identity/v1/oauth2/token`), Browse API `item_summary/search` endpoint.
- Daily call limit: 5,000. Usage has stayed well under budget even during heavy seeding/testing.

---

## 3. Key Bugs Found & Fixed (Session 1)

### a) Stale import bug — fixed early, routine cleanup.

### b) eBay keyset compliance block — resolved via exemption with eBay.

### c) Notification-throttling flood
Original poller had no cap on outgoing notification emails. Fixed with daily alert caps + a cold-start guard against false-positive "price drop" alerts from sparse early data.

### d) Data contamination (seed data mixup)
Wrong/fake seed data ended up mixed into the **dev in-memory DB** (`dev_server.py`), not the real working DB. Cleaned up. This directly motivated the `owner` field design below — explicit separation over inferred assumptions.

### e) Duplicate poller implementations → consolidated with explicit ownership model
Two inconsistent poller scripts existed. Merging them risked public site activity (visitor searches) triggering CD's *personal* email notifications — same failure class as (d).

**Fix — `owner` field on `tracked_items`:**
- `owner=NULL, is_seeded=True` → seed item (curated baseline content)
- `owner=NULL, is_seeded=False` → public user search
- `owner='durantco', is_seeded=False` → CD's personal item

Design details:
- Only `manage_items.py add` (CLI) sets `owner`, read from `POLLER_OWNER` env var — set once, never guessed.
- `/api/search` and `seed_tracked_item()` always leave `owner=NULL`.
- Notification routing happens in the unified poller, gated at the dispatch boundary:
  - `process_alerts()` runs for all items (public subscriber alerts — currently unused, no subscribers yet).
  - Personal `notifier.notify()` only fires when `item.owner is not None`.
- If a public visitor searches something CD later adds personally via CLI, the row gets "claimed" (owner updated), logged explicitly, not silently duplicated or silently ignored.
- Hard guard: if `POLLER_OWNER` is unset/empty/whitespace, `manage_items.py add` refuses (`SystemExit(1)`) rather than silently mis-owning an item.

**Testing:** Regression tests included `test_public_item_never_triggers_personal_notify`, `test_seeded_item_never_triggers_personal_notify`, `test_owner_item_triggers_personal_notify`, `test_public_alerts_fire_for_all_items`, `test_add_claims_existing_public_item`, `test_add_refuses_without_poller_owner`, `test_add_refuses_with_empty_poller_owner`, `test_claim_existing_unowned_item`, `test_claim_already_owned_is_noop`.

Files: `resale_price_agent/db.py`, `resale_price_agent/poller.py` (now the single real poller — root `poller.py` is a thin CLI wrapper), `manage_items.py`.

---

## 4. Seeding & First Real Data Run (Session 1)

- Confirmed the working DB was clean before seeding (only CD's personal item + its prior snapshots — the dev-DB contamination never touched this database).
- `seed_all()` created all 75 curated seed items across ~10 categories. Zero failures.
- `poll_all_items()` fetched real eBay data for all 76 items → 3,896 total snapshots. One expected outlier (Sonos Era 300, 46 snapshots — eBay simply had fewer live listings, not a failure).
- CD's personal Jordan 4 item correctly triggered 4 notification emails during this run (capped at 3 price-drop alerts + 1 buy_now/day), confirming owner-gated routing worked on first real use.

---

## 5. Frontend Issues Found & Fixed (Session 1)

### a) Dev vs. real backend confusion
`localhost:5173` was initially pointed at `dev_server.py` (mock data), not the real Flask backend + real DB. Fixed by explicitly restarting Flask against the real DB. **Lesson: always confirm which backend is actually running before trusting what's on screen.**

### b) "View on eBay" links initially broken
Root cause was isolated to `dev_server.py`'s **mock** item ID generator (5-6 digit fake IDs vs. eBay's real 12-13 digit format) — the real DB's `item_url` values were correct all along. Fixed the mock generator; no backend/schema change needed.
Added `RecentListings` component (frontend-only) on the item detail page: latest poll's listings, cheapest-first, capped at ~10, each linking out via `target="_blank" rel="noopener noreferrer"`.

### c) Accessory/category contamination bug (major, multi-step fix)
Bare keyword eBay queries (no category filtering) let cheap accessories (cases, screen protectors, replacement parts, wrong-model items) match real product searches and pollute price stats.
- **Scope:** ~40+ of 75 seed items affected. Sneakers/streetwear had a *different*, still-unsolved problem — counterfeit/replica listings (flagged, not addressed).
- **Fix, phase 1 — category filtering:** Added `ebay_category_id` to all 75 seed items, passed via `category_ids` to the Browse API.
- **Fix, phase 2 — historical outlier filter:** `filter_outliers()` drops snapshots below 40% of rolling median once 5+ prior snapshots exist.
- Explicitly deferred: per-item price floors (skipped as unnecessary overhead) and sneaker counterfeit detection (separate problem, needs different signals like seller feedback/authenticity flags).

---

## 6. Data Wipe + Clean Re-poll, Round 1 (Session 2)

Wiped all contaminated data and re-collected clean:
- **Wipe:** 3,896 snapshots + 240 decisions deleted. All 76 `tracked_items` preserved (owner/is_seeded/category intact), status reset to `collecting`.
- **Re-poll (62 of 76 items):** succeeded first pass — 2,959 snapshots, 202 decisions, 61 items reached `active` status.
- **14 items failed** (zero snapshots): 8 trading card items (wrong/too-narrow category `183475`) + 6 niche items (Sony Walkman, GoPro, North Face Nuptse, Stanley Tumbler, YETI Cooler, Dyson Airwrap — likely wrong category IDs).
- **Root cause confirmed as category ID mapping errors, not a crash** — the "5-minute timeout" that looked like a failure was actually the process finishing in ~295 seconds and separately hitting the Gemini 20/day rate limit; unrelated to the 14 failures.
- Researched and corrected category IDs for all 14 → re-polled successfully: 610 new snapshots, 14/14 success.

**Result after round 1:** 76 items with 0 zero-snapshot items, 3,569 total snapshots, 202 decisions, 74 active / 2 still `collecting` (MTG MH3 Collector Box, Contax T2 — genuinely only 2 real eBay listings each).

**Spot-checks:** PS5 "cleanest it's ever been," AirPods Pro 2 clean, Jordan 4 personal data intact. **But:** Z Flip 5 still had one straggler — a $27.36 screen protector survived, because it was that item's *first* poll post-fix and the outlier filter requires 5+ prior snapshots to activate (cold-start gap, unaddressed at this point).

---

## 7. Cold-Start Filtering Fix + Targeted Cleanup (Session 3)

An external review (second AI opinion CD sought) correctly diagnosed two remaining problems and proposed a sequenced fix plan, which was followed:

### a) Cold-start filtering gap — fixed
The historical 40%-of-median filter literally cannot fire on an item's first-ever poll (no history to compare against) — this is exactly why the Z Flip 5 screen protector survived the "clean" re-poll.
**Fix:** `filter_outliers()` now has two tiers — historical median (existing, 5+ snapshots) OR **batch median** (new: when no history exists but the current poll batch has 8+ listings). Both use the same 40% floor. `min_batch=8` guard prevents unreliable filtering on very small result sets (e.g. MTG MH3, Contax T2 — only 2 listings each, never filtered).
**Tests added (3):** `test_cold_start_drops_accessory_outlier` (Z Flip regression), `test_cold_start_skips_small_batch` (MTG MH3 regression), `test_cold_start_keeps_uniform_cheap_items` (Stanley Tumbler — legitimately cheap items preserved).
**253 tests passing** after this fix.

### b) Targeted cleanup of pre-existing contamination
The cold-start fix only protects items on their *first* poll going forward — it doesn't retroactively clean the 44 items that already had contaminated history from round 1.
**Analysis before deleting:** Verified the raw median (used for the 40% floor) wasn't itself skewed by junk listings — compared raw vs. 10%-trimmed median for every affected item, all within 5%, confirming the raw median was a safe basis for the cleanup.
**Executed:** Deleted 243 contaminated snapshot rows across 44 items (worst offender: Pokemon Scarlet Violet Booster Box, 46% contaminated). Confirmed the Z Flip 5's $27.36 screen protector and an $85.99 broken-screen phone were both removed — cheapest Z Flip 5 listing is now $124.99, a real (if cosmetically damaged) phone.
**Decisions left untouched:** 202 decisions preserved as-is, including ~27 that were originally triggered by junk listings — left in place as historical record since the price-drop detector recomputes fresh each poll; deleting them would gain nothing.

**Final DB state after this session:** 76 items, **3,326 snapshots**, 202 decisions, 74 active / 2 collecting, Jordan 4 personal item intact (50 clean snapshots, owner=durantco).

**Gemini note:** Only ~19 of 76 items have LLM (buy/wait/skip) decisions — the 20/day Gemini quota was hit mid-poll during round 1. The rest have snapshots but no LLM reasoning yet; will fill in as quota resets on subsequent polls. **Important finding: eBay data collection is NOT blocked by Gemini failures** — snapshots are inserted before the LLM call runs, and a 429 just produces a `skipped` decision rather than failing the item. So this is a reasoning-layer gap, not a data-collection problem.

**Commits pushed this session (5):**
- `ee433c0` — RecentListings component
- `a266bea` — Fix mock eBay item IDs (dev server)
- `410564a` — eBay category filtering + historical outlier detection
- `fd102ee` — Fix 14 broken category IDs
- `a0dff04` — Cold-start batch median filter

---

## 8. Critical Correction: SQLite, Not Postgres

**Earlier documentation (and assumptions throughout this project) incorrectly referred to the working database as "production PostgreSQL."** This has now been explicitly verified and corrected:

- **Confirmed: the project has been running on a local SQLite file (`resale_agent.db`) the entire time.** No `DATABASE_URL` is configured in `.env`.
- **Everything described in Sections 4-7 — all 76 items, all snapshots, all decisions, CD's personal Jordan 4 data — lives in this local SQLite file, not a hosted database.**
- **This has direct, unresolved implications for Render deployment:** a Render background worker cannot read a file sitting on CD's laptop. Before Render can be set up as planned, this needs:
  1. A real hosted Postgres instance provisioned (Render offers this)
  2. A `DATABASE_URL` configured and verified
  3. A decision on whether to migrate the current SQLite data into Postgres, or start fresh
- **This is an open item, not yet resolved or scheduled.** Do not proceed with Render setup assuming Postgres is already live — it is not.

---

## 9. Reset Tooling — Fixed (Session 4)

`reset_data.py` is now a safe, tested reset mechanism:
- Uses the actual `snapshots` table (the stale `listing_snapshots` reference is gone).
- Prints exact snapshot, decision, tracked-item, status-change, and alert counts before any write.
- Refuses to write unless the caller passes the explicit `--confirm` flag (the callable API likewise requires `confirmed=True`).
- Deletes snapshots and decisions together in one transaction, then resets non-collecting item statuses to `collecting`.
- Preserves every `tracked_items` row and its ownership, seed flag, eBay category ID, and other configuration. Alert subscriptions are also preserved.
- Running the command without `--confirm` against the working database safely previewed 3,326 snapshots, 202 decisions, 76 preserved tracked items, 74 status changes, and 0 alerts, then exited without changing data.

Three reset-specific tests cover confirmation refusal/no mutation, exact preview counts, successful transactional cleanup, status reset, and preservation of tracked-item configuration and alerts. Full suite: **256 passed, 1 third-party Google GenAI deprecation warning**.

---

## 10. Deferred / Queued Ideas (Not Yet Built)

### a) Clickable price-chart data points
CD wants each point on `PriceChart` to be clickable, opening that snapshot's real eBay listing (`item_url`) in a new tab — same pattern as `RecentListings`. **Status: queued, ready to start** now that the underlying data is verified clean (post Section 7 cleanup).

### b) Reusable wipe/reset concept — mechanism built, no reset pending
The repaired `reset_data.py` now implements the reusable safety valve: preview exact counts by running without arguments, then execute only with the explicit `--confirm` flag. **No reset was executed while repairing or testing it.** Any future wipe still requires separate, explicit approval after reviewing the live preview.

### c) Sneaker/streetwear counterfeit problem
Not addressed. Category filtering doesn't help since fakes share the same real category as genuine items. Will likely need a different signal (seller feedback score, eBay's authenticity guarantee flag if exposed via API, or accept as a known limitation with a UI disclaimer).

### d) Gemini/polling decoupling (deferred; optional analysis only)
**Diagnosis complete (Session 3):** Currently, LLM reasoning happens inline in the same per-item loop as eBay fetch + snapshot insert (`poller.py` ~lines 186-191). Snapshots are already committed before the LLM call, so eBay data collection already survives Gemini rate-limit failures today (confirmed — see Section 7).

**What's missing for a full decouple:**
1. No "needs decision" query — no way to find items with new snapshots but no LLM decision since their last poll (would need a `last_decided_at` timestamp or a join between snapshots/decisions by time).
2. `_build_listing_summary` currently takes the in-memory snapshot list from the current poll — a separate later LLM pass would need to reconstruct this from stored snapshots instead.
3. `process_alerts` currently depends on the LLM result — if reasoning runs later/separately, alerts would also fire later.

**Formerly proposed architecture (superseded by Section 14):**
- Phase A (poll): `eBay → snapshots → signals → price_drop detection → store`
- Phase B (reason): `items needing decisions → compute_signals → LLM → store decision → alerts → notifications`

This backlog is no longer a core-product task. A similar queue may be useful later for optional `llm_analysis`, but Gemini will not generate or override the authoritative recommendation.

---

## 11. Not Yet Started

- **SQLite → Postgres migration / Render deployment** — blocked on the Section 8 correction. This is now the most significant open architectural item.
- **A dedicated personal "test item"** for CD to watch agent behavior (notifications, trend accumulation) over several days once things are stable.
- **Public alert subscriptions** — `process_alerts()` path exists and is tested, but the `alerts` table is empty; no real users yet since the site isn't public-facing.
- **One final controlled wipe before launch** (Section 10b concept) — the mechanism is ready, but do not run it without a separate explicit approval after reviewing a fresh preview.

---

## 12. Standing Principles Established This Project

- **Personal vs. public separation must be explicit in the schema, never inferred** — the throughline from the original contamination bug through the `owner` field design.
- **CD's personal item is intentionally not separate infrastructure** — it's a fully public, fully visible tracked item like any other; the only difference is CD also gets a personal email alert on top of the same public behavior everyone else gets (explicitly confirmed as desired).
- **The system is demand-driven, not exhaustive** — not trying to track "every item on eBay." Curated seed list (baseline content) + real user searches, growing organically. No architecture changes needed as this scales into the hundreds/low-thousands.
- **Diagnostic-before-destructive is the standing pattern** — every deletion or reset (DB cleanup checks, both wipes, the targeted cleanup) has been preceded by an explicit "report what's there / propose the plan, don't execute yet" step, with exact row counts reported before any delete runs. **This must continue for any future destructive action, including the eventual SQLite→Postgres migration.**
- **Verify claims against the actual codebase/DB state rather than trusting prior documentation** — the SQLite/Postgres correction (Section 8) is a direct lesson: earlier assumptions were wrong and went uncorrected for a while. When in doubt, check.

---

## 13. Session 4 Handoff

### Completed
- Repaired and hardened `reset_data.py` as described in Section 9.
- Added `tests/test_reset_data.py` with 3 safety/preservation tests.
- Ran the safe preview path only; no destructive reset was performed.
- Verified the database remained unchanged after the preview and test run: **76 tracked items, 3,326 snapshots, 202 decisions, 0 alerts, 74 active / 2 collecting**.
- Full test suite: **256 passed in 0.70s**, with one non-blocking deprecation warning from `google.genai` under Python 3.14.

### Unresolved
- Gemini reasoning remains inline and externally quota-limited; 57 items still lack a successful LLM reasoning decision.
- Residual partial-item/accessory results and sneaker/streetwear counterfeit detection remain open data-quality issues.
- SQLite → hosted Postgres migration and Render deployment remain intentionally deferred.
- Clickable price-chart listing links remain queued.

### Recommended next task
**Superseded by the approved deterministic direction and Phase 2 recommendation in Section 14.** Do not resume core Gemini/polling decoupling.

---

## 14. Approved Decision-Engine Direction (Session 5)

The product's recommendation architecture has changed before the previously planned Gemini backlog/decoupling work was implemented:

- **Deterministic/statistical `BUY` / `WAIT` / `SKIP` is now the authoritative recommendation system.**
- Every tracked item should eventually receive a recommendation independently of Gemini availability or quota.
- Gemini is being repositioned as an optional `llm_analysis` explanation/advanced-analysis layer.
- Gemini analysis must never override the deterministic action.
- The previously proposed Gemini backlog/decoupling work is deferred unless it is useful later for optional AI analysis.

The reason for the change is scalability and reliability: the catalogue already contains 76 tracked items while the observed Gemini quota is roughly 20 reasoning calls per day. Core recommendations must remain available to every tracked item and user without depending on an external LLM quota.

**Approved pipeline:**

`eBay → filtering → snapshots → longitudinal statistical signals → deterministic BUY / WAIT / SKIP`

### Phase 1 completed

- Added an explicit UUID `poll_batch_id` to snapshots. Every `insert_snapshots()` call creates one batch unless a caller supplies a batch ID explicitly.
- Added a small additive schema migration. Existing rows are backfilled deterministically by tracked item + their formerly shared snapshot timestamp, preserving the legacy batch grouping without deleting or rewriting snapshot content.
- Added an `(tracked_item_id, poll_batch_id)` index.
- Reworked `compute_signals()` so price and listing direction compare distinct poll batches. A single fetch can no longer manufacture a longitudinal trend by splitting its listings in half.
- `sufficient_data` now requires at least 5 snapshots across at least 2 distinct poll batches.
- Added batch count, history span, latest-batch time and median, prior batch-median baseline, median of batch medians, 25th/75th percentiles, IQR, unique eBay listing count, latest-batch unique count, and freshness.
- Listing-volume trends use unique eBay IDs per batch rather than raw snapshot rows.
- Fixed price-drop orchestration so the current poll batch is excluded from its own historical baseline. The existing cold-start outlier filter was not changed.
- Kept the Gemini implementation in place. No deterministic `BUY` / `WAIT` / `SKIP` formula, decision storage, API/UI changes, or notification routing changes were added in Phase 1.

**Migration validation:** The additive migration was exercised against a temporary copy of the real 3,326-snapshot SQLite database: all rows received non-empty batch IDs, grouped into the expected 76 item/batch pairs, and no rows were lost. The working database itself was not modified during this task; the migration will run automatically the next time the application opens it through `get_engine()`.

**Tests:** 262 passed, 1 non-blocking third-party `google.genai` deprecation warning. New coverage verifies automatic/separate batch IDs, legacy migration/backfill grouping, one-batch insufficiency, multi-batch price and supply direction, robust statistics, unique-listing counts, history span/freshness, and exclusion of the current batch from price-drop history.

### Recommended Phase 2

Implement a pure, versioned deterministic recommendation module and idempotent `deterministic_recommendation` storage. Start with explicit evidence/confidence gates (especially poll-batch maturity), then table-driven `BUY` / `WAIT` / `SKIP` rules. Keep Gemini non-authoritative and keep notification routing unchanged until the deterministic results and API selection behavior are proven with tests.

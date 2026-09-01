"""Deterministic price-drop detection — pure Python, no LLM."""

import json
import logging
from datetime import datetime, timedelta, timezone

from resale_price_agent.db import (
    get_recent_alerts,
    get_snapshots_for_item,
    insert_decision,
)

log = logging.getLogger(__name__)

# Minimum number of historical snapshots needed to compute a meaningful
# rolling average.  Below this threshold the average check is skipped.
MIN_HISTORY_SNAPSHOTS = 5

# Default lookback window for computing the rolling average.
ROLLING_WINDOW_DAYS = 14

# Default threshold: a new listing must be at least this fraction below
# the rolling average to trigger an alert (0.12 = 12%).
DROP_THRESHOLD_PCT = 0.12

# --- Throttling defaults ---
# Don't re-alert on the same eBay listing within this many hours.
DEDUP_WINDOW_HOURS = 24

# Maximum alerts per tracked item per calendar day (UTC).  Prevents inbox
# flooding when many listings qualify at once.
DAILY_ALERT_CAP = 10


def _get_already_alerted_ids(engine, tracked_item_id: int, window_hours: int) -> set[str]:
    """Return eBay listing IDs that already triggered an alert within *window_hours*."""
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    recent = get_recent_alerts(engine, tracked_item_id, since=since)
    seen: set[str] = set()
    for dec in recent:
        raw = dec.get("computed_signals") or "{}"
        try:
            signals = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        ebay_id = signals.get("ebay_item_id", "")
        if ebay_id:
            seen.add(ebay_id)
    return seen


def _count_today_alerts(engine, tracked_item_id: int) -> int:
    """Count price-drop alerts already fired today (UTC) for this tracked item."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    return len(get_recent_alerts(engine, tracked_item_id, since=today_start))


def check_price_drops(
    engine,
    tracked_item_id: int,
    new_snapshots: list[dict],
    target_price: float | None = None,
    drop_threshold: float = DROP_THRESHOLD_PCT,
    window_days: int = ROLLING_WINDOW_DAYS,
    min_history: int = MIN_HISTORY_SNAPSHOTS,
    dedup_window_hours: int = DEDUP_WINDOW_HOURS,
    daily_cap: int = DAILY_ALERT_CAP,
) -> list[int]:
    """Check new snapshots for price drops and log alerts.

    Returns a list of decision IDs for any alerts that were logged.

    Throttling:
    - Skips listings that already triggered an alert within
      *dedup_window_hours*.
    - Stops once *daily_cap* alerts have been fired today (UTC)
      for this tracked item.
    """
    if not new_snapshots:
        return []

    alerts: list[int] = []

    # --- Throttle state ---
    already_alerted = _get_already_alerted_ids(engine, tracked_item_id, dedup_window_hours)
    today_count = _count_today_alerts(engine, tracked_item_id)

    # --- Compute rolling average from history (if enough data) ---
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    history = get_snapshots_for_item(engine, tracked_item_id, since=since)
    prices = [s["price"] for s in history]

    rolling_avg = None
    if len(prices) >= min_history:
        rolling_avg = sum(prices) / len(prices)

    for snap in new_snapshots:
        # --- Daily cap check ---
        if today_count + len(alerts) >= daily_cap:
            log.info(
                "  Tracked item #%d: daily alert cap (%d) reached — skipping remaining.",
                tracked_item_id, daily_cap,
            )
            break

        ebay_item_id = snap.get("ebay_item_id", "")

        # --- Dedup check ---
        if ebay_item_id and ebay_item_id in already_alerted:
            log.debug(
                "  Tracked item #%d: skipping listing %s (already alerted within %dh)",
                tracked_item_id, ebay_item_id, dedup_window_hours,
            )
            continue

        price = snap["price"]
        reasons = []
        signals = {}

        # --- Target price check ---
        if target_price is not None and price <= target_price:
            reasons.append(
                f"${price:.2f} is at or below target price ${target_price:.2f}"
            )
            signals["target_price"] = target_price

        # --- Rolling average check ---
        if rolling_avg is not None:
            pct_below = (rolling_avg - price) / rolling_avg
            signals["rolling_avg"] = round(rolling_avg, 2)
            signals["pct_below_avg"] = round(pct_below * 100, 2)
            signals["window_days"] = window_days
            signals["history_count"] = len(prices)

            if pct_below >= drop_threshold:
                reasons.append(
                    f"${price:.2f} is {pct_below * 100:.1f}% below "
                    f"{window_days}-day average ${rolling_avg:.2f}"
                )

        if not reasons:
            continue

        reasoning = "; ".join(reasons)
        signals["listing_price"] = price
        signals["ebay_item_id"] = ebay_item_id
        signals["title"] = snap.get("title", "")
        signals["item_url"] = snap.get("item_url", "")

        dec_id = insert_decision(
            engine,
            tracked_item_id,
            "price_drop_alert",
            computed_signals=json.dumps(signals),
            reasoning=reasoning,
        )
        alerts.append(dec_id)
        # Also mark this listing as alerted so later snapshots in the
        # same batch don't duplicate it.
        if ebay_item_id:
            already_alerted.add(ebay_item_id)
        log.info(
            "  ALERT #%d for tracked item #%d: %s",
            dec_id, tracked_item_id, reasoning,
        )

    return alerts

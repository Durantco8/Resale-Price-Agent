"""Deterministic price-drop detection — pure Python, no LLM."""

import json
import logging
from datetime import datetime, timedelta, timezone

from resale_price_agent.db import (
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


def check_price_drops(
    engine,
    tracked_item_id: int,
    new_snapshots: list[dict],
    target_price: float | None = None,
    drop_threshold: float = DROP_THRESHOLD_PCT,
    window_days: int = ROLLING_WINDOW_DAYS,
    min_history: int = MIN_HISTORY_SNAPSHOTS,
) -> list[int]:
    """Check new snapshots for price drops and log alerts.

    Returns a list of decision IDs for any alerts that were logged.
    """
    if not new_snapshots:
        return []

    alerts: list[int] = []

    # --- Compute rolling average from history (if enough data) ---
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    history = get_snapshots_for_item(engine, tracked_item_id, since=since)
    prices = [s["price"] for s in history]

    rolling_avg = None
    if len(prices) >= min_history:
        rolling_avg = sum(prices) / len(prices)

    for snap in new_snapshots:
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
        signals["ebay_item_id"] = snap.get("ebay_item_id", "")
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
        log.info(
            "  ALERT #%d for tracked item #%d: %s",
            dec_id, tracked_item_id, reasoning,
        )

    return alerts

"""Shared polling loop — fetch, store, compute signals, run LLM.

Standalone importable function designed to be called by a background
worker (e.g. APScheduler) or directly from tests.  All external
dependencies (eBay client, LLM client, DB engine) are injected so the
full pipeline runs against fakes with zero network calls.

One item's failure never blocks the others.
"""

import json
import logging

from resale_price_agent.alerts import process_alerts
from resale_price_agent.db import (
    get_all_tracked_items,
    get_snapshots_for_item,
    insert_snapshots,
    set_tracked_item_status,
)
from resale_price_agent.ebay_client import ListingSnapshot
from resale_price_agent.llm_reasoning import get_llm_decision
from resale_price_agent.signals import compute_signals

log = logging.getLogger(__name__)

# Number of total snapshots at which a tracked item transitions from
# "collecting" to "active".  Matches MIN_SNAPSHOTS in signals.py — below
# this the LLM layer skips anyway since trends can't be computed.
STATUS_THRESHOLD = 5

# Recommended polling interval for production use.  Each poll cycle makes
# one eBay Browse API call per tracked item.  The daily API limit is 5,000
# calls.  At 75 items and a 3-hour interval:
#   8 cycles/day × 75 items = 600 calls/day (12% of daily budget).
# Headroom allows for user-initiated searches and future item growth.
POLL_INTERVAL_HOURS = 3


def snapshot_to_dict(snap: ListingSnapshot) -> dict:
    """Convert a ListingSnapshot dataclass to a dict matching the DB schema."""
    return {
        "ebay_item_id": snap.item_id,
        "title": snap.title,
        "price": snap.price_amount,
        "currency": snap.price_currency,
        "condition": snap.condition,
        "seller_feedback_score": snap.seller_feedback_score,
        "shipping_cost": snap.shipping_cost,
        "item_location": snap.item_location,
        "buying_format": (
            ", ".join(snap.buying_options) if snap.buying_options else None
        ),
        "item_url": snap.item_url,
    }


def _build_listing_summary(snapshot_dicts: list[dict]) -> str:
    """Build a short text summary of current listings for the LLM prompt."""
    if not snapshot_dicts:
        return "No listings found."
    prices = [s["price"] for s in snapshot_dicts]
    lines = [
        f"{len(snapshot_dicts)} listing(s), "
        f"${min(prices):.2f}\u2013${max(prices):.2f}"
    ]
    for s in snapshot_dicts[:5]:
        fmt = s.get("buying_format") or "unknown"
        lines.append(f"  ${s['price']:.2f} \u2014 {s.get('condition', '?')} [{fmt}]")
    if len(snapshot_dicts) > 5:
        lines.append(f"  ... and {len(snapshot_dicts) - 5} more")
    return "\n".join(lines)


def poll_all_items(
    engine,
    ebay_client,
    llm_client=None,
    send_fn=None,
    status_threshold: int = STATUS_THRESHOLD,
) -> dict:
    """Poll every tracked item: fetch listings, store, compute, decide, alert.

    *send_fn* is an injectable email sender ``(to, subject, body) -> None``.
    Pass ``None`` to skip alert emails entirely.

    Returns a summary dict for observability/logging.
    """
    items = get_all_tracked_items(engine)
    if not items:
        log.info("No tracked items \u2014 nothing to poll.")
        return {
            "processed": 0, "failed": 0,
            "total_snapshots": 0, "alerts_sent": 0,
        }

    log.info("Polling %d tracked item(s)...", len(items))

    processed = 0
    failed = 0
    total_snapshots = 0
    total_alerts_sent = 0

    for item in items:
        item_id = item["id"]
        query = item["search_query"]

        try:
            # --- Fetch and store ---
            listings = ebay_client.search_listings(query)
            snapshot_dicts = [snapshot_to_dict(s) for s in listings]
            count = insert_snapshots(engine, item_id, snapshot_dicts)
            total_snapshots += count
            processed += 1
            log.info(
                "  #%d \"%s\" \u2014 %d listing(s) stored",
                item_id, query, count,
            )

            # --- Status transition ---
            if item["status"] == "collecting":
                all_snaps = get_snapshots_for_item(engine, item_id)
                if len(all_snaps) >= status_threshold:
                    set_tracked_item_status(engine, item_id, "active")
                    log.info(
                        "  #%d \"%s\" \u2014 status \u2192 active "
                        "(%d snapshots)",
                        item_id, query, len(all_snaps),
                    )

            # --- Signal computation + LLM decision ---
            signals = compute_signals(engine, item_id)
            listing_summary = _build_listing_summary(snapshot_dicts)
            llm_kwargs = {"client": llm_client} if llm_client else {}
            llm_result = get_llm_decision(
                engine, item_id, signals, listing_summary, **llm_kwargs,
            )

            # --- Alert notifications ---
            if send_fn is not None:
                sent = process_alerts(
                    engine, item, snapshot_dicts, llm_result, send_fn,
                )
                total_alerts_sent += sent

        except Exception:
            failed += 1
            log.exception("  #%d \"%s\" \u2014 FAILED", item_id, query)

    log.info(
        "Poll complete: %d processed, %d failed, %d snapshot(s), "
        "%d alert(s) sent.",
        processed, failed, total_snapshots, total_alerts_sent,
    )
    return {
        "processed": processed,
        "failed": failed,
        "total_snapshots": total_snapshots,
        "alerts_sent": total_alerts_sent,
    }

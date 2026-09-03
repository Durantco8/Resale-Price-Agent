"""Unified polling loop — fetch, store, detect, reason, notify.

Single polling function used by both the CLI entry point and the dev
server.  All external dependencies (eBay client, LLM client, DB
engine, email sender) are injected so the full pipeline runs against
fakes with zero network calls.

One item's failure never blocks the others.
"""

import json
import logging
import statistics
import uuid

from resale_price_agent.alerts import process_alerts
from resale_price_agent.db import (
    get_all_tracked_items,
    get_decisions_for_item,
    get_snapshots_for_item,
    insert_snapshots,
    set_tracked_item_status,
)
from resale_price_agent.ebay_client import ListingSnapshot
from resale_price_agent.llm_reasoning import get_llm_decision
from resale_price_agent.notifier import notify
from resale_price_agent.price_drop import check_price_drops
from resale_price_agent.recommendation import evaluate, record_recommendation
from resale_price_agent.signals import compute_signals

log = logging.getLogger(__name__)

STATUS_THRESHOLD = 5

POLL_INTERVAL_HOURS = 3

# Snapshots priced below this fraction of the median are dropped as
# likely accessories/parts.  Applied against historical data when
# available, or against the current batch on cold start.
OUTLIER_FLOOR_RATIO = 0.4
MIN_SNAPSHOTS_FOR_FILTER = 5   # historical median threshold
MIN_BATCH_FOR_FILTER = 8       # cold-start batch median threshold


def snapshot_to_dict(snap: ListingSnapshot) -> dict:
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


def filter_outliers(
    engine, item_id: int, snapshot_dicts: list[dict],
    floor_ratio: float = OUTLIER_FLOOR_RATIO,
    min_snapshots: int = MIN_SNAPSHOTS_FOR_FILTER,
    min_batch: int = MIN_BATCH_FOR_FILTER,
) -> list[dict]:
    """Drop snapshots priced suspiciously below the median.

    Uses historical snapshots when enough exist, otherwise falls back
    to the current batch's own median for cold-start filtering.
    Skips filtering entirely when neither source has enough data.
    """
    if not snapshot_dicts:
        return snapshot_dicts

    existing = get_snapshots_for_item(engine, item_id)

    if len(existing) >= min_snapshots:
        # Established item — use historical median
        median_price = statistics.median(s["price"] for s in existing)
        source = "historical"
    elif len(snapshot_dicts) >= min_batch:
        # Cold start — use the current batch's median
        median_price = statistics.median(s["price"] for s in snapshot_dicts)
        source = "batch"
    else:
        # Not enough data from either source
        return snapshot_dicts

    floor_price = median_price * floor_ratio

    kept = [s for s in snapshot_dicts if s["price"] >= floor_price]
    dropped = len(snapshot_dicts) - len(kept)
    if dropped:
        log.info(
            "  #%d — dropped %d outlier(s) below $%.2f "
            "(%.0f%% of %s median $%.2f)",
            item_id, dropped, floor_price, floor_ratio * 100,
            source, median_price,
        )
    return kept


def poll_all_items(
    engine,
    ebay_client,
    llm_client=None,
    send_fn=None,
    notify_send_fn=None,
    notify_recipient=None,
    skip_ebay=False,
    status_threshold: int = STATUS_THRESHOLD,
) -> dict:
    """Poll every tracked item: fetch, store, detect, reason, notify.

    *send_fn* — injectable email sender for public alert subscriptions.
    *notify_send_fn* — injectable email sender for personal notifications.
    *notify_recipient* — personal notification email address (NOTIFY_TO).
        Personal notifications only fire for items with a non-NULL owner.
    *skip_ebay* — if True, reuse existing snapshots instead of fetching.

    Returns a summary dict.
    """
    items = get_all_tracked_items(engine)
    if not items:
        log.info("No tracked items \u2014 nothing to poll.")
        return {
            "processed": 0, "failed": 0, "total_snapshots": 0,
            "alerts_sent": 0, "notifications": 0,
        }

    log.info("Polling %d tracked item(s)...", len(items))

    processed = 0
    failed = 0
    total_snapshots = 0
    total_alerts_sent = 0
    total_notifications = 0

    for item in items:
        item_id = item["id"]
        query = item["search_query"]
        target_price = item.get("target_price")

        try:
            # --- Fetch and store ---
            prior_snapshots = None
            if skip_ebay:
                snapshot_dicts = get_snapshots_for_item(engine, item_id, limit=50)
                processed += 1
                log.info(
                    "  #%d \"%s\" \u2014 skipped eBay, using %d existing snapshot(s)",
                    item_id, query, len(snapshot_dicts),
                )
            else:
                # Capture history before inserting this poll batch.  Price-drop
                # detection must never use the batch it is evaluating as its
                # own historical baseline.
                prior_snapshots = get_snapshots_for_item(engine, item_id)
                category_ids = item.get("ebay_category_id")
                listings = ebay_client.search_listings(
                    query, category_ids=category_ids,
                )
                snapshot_dicts = [snapshot_to_dict(s) for s in listings]
                snapshot_dicts = filter_outliers(engine, item_id, snapshot_dicts)
                batch_id = uuid.uuid4().hex
                count = insert_snapshots(
                    engine, item_id, snapshot_dicts, poll_batch_id=batch_id,
                )
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
                        "  #%d \"%s\" \u2014 status \u2192 active (%d snapshots)",
                        item_id, query, len(all_snaps),
                    )

            # --- Price-drop detection ---
            alert_ids = check_price_drops(
                engine, item_id, snapshot_dicts, target_price=target_price,
                history_snapshots=prior_snapshots,
            )

            # --- Signal computation + deterministic recommendation ---
            signals = compute_signals(engine, item_id)
            if not skip_ebay:
                rec = evaluate(signals)
                record_recommendation(engine, item_id, batch_id, rec)

            # --- LLM decision ---
            listing_summary = _build_listing_summary(snapshot_dicts)
            llm_kwargs = {"client": llm_client} if llm_client else {}
            llm_result = get_llm_decision(
                engine, item_id, signals, listing_summary, **llm_kwargs,
            )

            # --- Public subscriber alerts (all items) ---
            if send_fn is not None:
                sent = process_alerts(
                    engine, item, snapshot_dicts, llm_result, send_fn,
                )
                total_alerts_sent += sent

            # --- Personal notifications (owner-gated) ---
            if item.get("owner") and notify_recipient:
                nf_kwargs = {}
                if notify_send_fn is not None:
                    nf_kwargs["send_fn"] = notify_send_fn

                for alert_id in alert_ids:
                    decisions = get_decisions_for_item(engine, item_id)
                    decision = next(
                        (d for d in decisions if d["id"] == alert_id), None,
                    )
                    if decision and notify(
                        query, decision,
                        recipient=notify_recipient, **nf_kwargs,
                    ):
                        total_notifications += 1

                if not llm_result.skipped and llm_result.action == "buy_now":
                    decisions = get_decisions_for_item(engine, item_id, limit=1)
                    if decisions and notify(
                        query, decisions[0],
                        recipient=notify_recipient, **nf_kwargs,
                    ):
                        total_notifications += 1

        except Exception:
            failed += 1
            log.exception("  #%d \"%s\" \u2014 FAILED", item_id, query)

    log.info(
        "Poll complete: %d processed, %d failed, %d snapshot(s), "
        "%d alert(s), %d notification(s).",
        processed, failed, total_snapshots, total_alerts_sent,
        total_notifications,
    )
    return {
        "processed": processed,
        "failed": failed,
        "total_snapshots": total_snapshots,
        "alerts_sent": total_alerts_sent,
        "notifications": total_notifications,
    }

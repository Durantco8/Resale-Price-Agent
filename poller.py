"""Full pipeline — poll, detect, reason, notify.

Ties together Stages 1 + 4-8: for each active tracked item, fetch
listings from eBay, store snapshots, run price-drop detection, compute
signals for the LLM, get the LLM's reasoning, and send notifications
for anything worth acting on.

One item's failure never blocks the others.
"""

import logging

from dotenv import load_dotenv
load_dotenv()

from resale_price_agent.db import (
    get_active_tracked_items,
    get_decisions_for_item,
    get_engine,
    get_snapshots_for_item,
    insert_snapshots,
)
from resale_price_agent.ebay_client import EbayClient, ListingSnapshot
from resale_price_agent.llm_reasoning import get_llm_decision
from resale_price_agent.notifier import notify
from resale_price_agent.price_drop import check_price_drops
from resale_price_agent.signals import compute_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


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
        "buying_format": ", ".join(snap.buying_options) if snap.buying_options else None,
        "item_url": snap.item_url,
    }


def _build_listing_summary(snapshot_dicts: list[dict]) -> str:
    """Build a short text summary of current listings for the LLM prompt."""
    if not snapshot_dicts:
        return "No listings found."
    prices = [s["price"] for s in snapshot_dicts]
    lines = [f"{len(snapshot_dicts)} listing(s), ${min(prices):.2f}–${max(prices):.2f}"]
    for s in snapshot_dicts[:5]:  # first 5 for context
        fmt = s.get("buying_format") or "unknown"
        lines.append(f"  ${s['price']:.2f} — {s.get('condition', '?')} [{fmt}]")
    if len(snapshot_dicts) > 5:
        lines.append(f"  ... and {len(snapshot_dicts) - 5} more")
    return "\n".join(lines)


def _send_notify(query, decision, send_fn, recipient):
    kwargs = {}
    if send_fn is not None:
        kwargs["send_fn"] = send_fn
    if recipient is not None:
        kwargs["recipient"] = recipient
    return notify(query, decision, **kwargs)


def poll_once(engine=None, ebay_client=None, llm_client=None, send_fn=None,
              notify_recipient=None, skip_ebay=False):
    if engine is None:
        engine = get_engine()
    if ebay_client is None and not skip_ebay:
        ebay_client = EbayClient()

    items = get_active_tracked_items(engine)
    if not items:
        log.info("No active tracked items — nothing to poll.")
        return {"processed": 0, "failed": 0, "total_listings": 0,
                "alerts": 0, "notifications": 0}

    log.info("Polling %d active tracked item(s)...", len(items))

    processed = 0
    failed = 0
    total_listings = 0
    total_alerts = 0
    total_notifications = 0

    for item in items:
        item_id = item["id"]
        query = item["search_query"]
        target_price = item.get("target_price")

        try:
            # --- Stage 4: Fetch and store ---
            if skip_ebay:
                snapshot_dicts = get_snapshots_for_item(engine, item_id, limit=50)
                processed += 1
                log.info(
                    "  #%d  \"%s\"  — skipped eBay, using %d existing snapshot(s)",
                    item_id, query, len(snapshot_dicts),
                )
            else:
                listings = ebay_client.search_listings(query)
                snapshot_dicts = [snapshot_to_dict(s) for s in listings]
                count = insert_snapshots(engine, item_id, snapshot_dicts)
                total_listings += count
                processed += 1
                log.info(
                    "  #%d  \"%s\"  — %d listing(s) stored",
                    item_id, query, count,
                )

            # --- Stage 5: Price-drop detection ---
            alert_ids = check_price_drops(
                engine, item_id, snapshot_dicts, target_price=target_price,
            )
            total_alerts += len(alert_ids)

            # Notify on price-drop alerts
            for alert_id in alert_ids:
                decisions = get_decisions_for_item(engine, item_id)
                decision = next(
                    (d for d in decisions if d["id"] == alert_id), None
                )
                if decision:
                    if _send_notify(query, decision, send_fn, notify_recipient):
                        total_notifications += 1

            # --- Stages 6+7: Signal computation + LLM reasoning ---
            signals = compute_signals(engine, item_id)
            listing_summary = _build_listing_summary(snapshot_dicts)

            llm_kwargs = {"client": llm_client} if llm_client else {}
            llm_result = get_llm_decision(
                engine, item_id, signals, listing_summary, **llm_kwargs,
            )

            # Notify on LLM buy_now
            if not llm_result.skipped and llm_result.action == "buy_now":
                decisions = get_decisions_for_item(engine, item_id, limit=1)
                if decisions:
                    if _send_notify(query, decisions[0], send_fn, notify_recipient):
                        total_notifications += 1

        except Exception:
            failed += 1
            log.exception(
                "  #%d  \"%s\"  — FAILED", item_id, query,
            )

    log.info(
        "Poll complete: %d processed, %d failed, %d listing(s), "
        "%d alert(s), %d notification(s).",
        processed, failed, total_listings, total_alerts, total_notifications,
    )
    return {
        "processed": processed,
        "failed": failed,
        "total_listings": total_listings,
        "alerts": total_alerts,
        "notifications": total_notifications,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the resale price agent pipeline.")
    parser.add_argument("--skip-ebay", action="store_true",
                        help="Skip eBay fetch, run detection on existing snapshots in DB")
    args = parser.parse_args()
    poll_once(skip_ebay=args.skip_ebay)

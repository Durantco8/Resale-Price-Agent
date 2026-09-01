"""Polling script — fetches listings for all active tracked items."""

import logging
from datetime import datetime, timezone

from resale_price_agent.db import (
    get_active_tracked_items,
    get_engine,
    insert_snapshots,
)
from resale_price_agent.ebay_client import EbayClient, ListingSnapshot

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


def poll_once(engine=None, ebay_client=None):
    if engine is None:
        engine = get_engine()
    if ebay_client is None:
        ebay_client = EbayClient()

    items = get_active_tracked_items(engine)
    if not items:
        log.info("No active tracked items — nothing to poll.")
        return {"processed": 0, "failed": 0, "total_listings": 0}

    log.info("Polling %d active tracked item(s)...", len(items))

    processed = 0
    failed = 0
    total_listings = 0

    for item in items:
        item_id = item["id"]
        query = item["search_query"]
        try:
            listings = ebay_client.search_listings(query)
            snapshot_dicts = [snapshot_to_dict(s) for s in listings]
            count = insert_snapshots(engine, item_id, snapshot_dicts)
            total_listings += count
            processed += 1
            log.info(
                "  #%d  \"%s\"  — %d listing(s) stored",
                item_id, query, count,
            )
        except Exception:
            failed += 1
            log.exception(
                "  #%d  \"%s\"  — FAILED", item_id, query,
            )

    log.info(
        "Poll complete: %d processed, %d failed, %d listing(s) stored.",
        processed, failed, total_listings,
    )
    return {"processed": processed, "failed": failed, "total_listings": total_listings}


if __name__ == "__main__":
    poll_once()

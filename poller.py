"""CLI entry point — runs the unified polling pipeline."""

import argparse
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import inspect, text

from resale_price_agent.db import get_engine, metadata, normalize_query
from resale_price_agent.ebay_client import EbayClient
from resale_price_agent.notifier import send_email
from resale_price_agent.poller import poll_all_items
from resale_price_agent.seed_list import SEED_ITEMS, seed_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    parser = argparse.ArgumentParser(
        description="Run the resale price agent pipeline.",
    )
    parser.add_argument(
        "--skip-ebay", action="store_true",
        help="Skip eBay fetch, run detection on existing snapshots in DB",
    )
    args = parser.parse_args()

    engine = get_engine()

    # Ensure schema exists
    metadata.create_all(engine)

    # Add 'category' column if missing (live Postgres migration)
    insp = inspect(engine)
    columns = {c["name"] for c in insp.get_columns("tracked_items")}
    if "category" not in columns:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE tracked_items ADD COLUMN category VARCHAR"
            ))
        logging.info("Added 'category' column to tracked_items")

    # Seed new Pokemon items
    result = seed_all(engine)
    if result["created"]:
        logging.info("Seeded %d new item(s)", result["created"])

    # Purge old non-Pokemon items (one-time cleanup)
    seed_queries = {normalize_query(e["query"]) for e in SEED_ITEMS}
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, normalized_query, display_name FROM tracked_items")).fetchall()
        to_delete = [r for r in rows if r[1] not in seed_queries]
        for row in to_delete:
            for table in ("recommendations", "decisions", "price_snapshots", "alerts"):
                try:
                    conn.execute(text(f"DELETE FROM {table} WHERE tracked_item_id = :id"), {"id": row[0]})
                except Exception:
                    pass
            conn.execute(text("DELETE FROM tracked_items WHERE id = :id"), {"id": row[0]})
        if to_delete:
            logging.info("Purged %d old item(s) not in seed list", len(to_delete))

    poll_all_items(
        engine=engine,
        ebay_client=None if args.skip_ebay else EbayClient(),
        send_fn=send_email,
        notify_send_fn=send_email,
        notify_recipient=os.environ.get("NOTIFY_TO", ""),
        skip_ebay=args.skip_ebay,
    )


if __name__ == "__main__":
    main()

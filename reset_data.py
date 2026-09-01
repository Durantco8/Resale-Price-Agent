"""Reset DB data — clears snapshots and decisions, preserves tracked items.

Usage:
    python reset_data.py --confirm
"""

import argparse
import sys

from dotenv import load_dotenv
load_dotenv()

from resale_price_agent.db import (
    get_all_tracked_items,
    get_engine,
    listing_snapshots,
    decisions,
)


def reset(engine):
    items = get_all_tracked_items(engine)

    with engine.begin() as conn:
        dec_result = conn.execute(decisions.delete())
        snap_result = conn.execute(listing_snapshots.delete())

    print(f"Deleted {snap_result.rowcount} snapshot(s) and {dec_result.rowcount} decision(s).")
    print(f"Tracked items preserved ({len(items)} item(s) still in watchlist).")


def main():
    parser = argparse.ArgumentParser(
        description="Clear all snapshots and decisions from the database. "
                    "Tracked items are preserved."
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Required flag to confirm the reset (prevents accidental runs).",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("This will delete ALL listing snapshots and decisions from the database.")
        print("Tracked items will be preserved.")
        print("\nRun with --confirm to proceed.")
        sys.exit(1)

    engine = get_engine()
    reset(engine)


if __name__ == "__main__":
    main()

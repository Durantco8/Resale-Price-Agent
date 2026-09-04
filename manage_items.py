"""CLI for managing tracked items in the Pokemon card price tracker."""

import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from resale_price_agent.db import (
    get_all_tracked_items,
    get_engine,
    get_or_create_tracked_item,
    get_tracked_item,
    metadata,
    set_tracked_item_status,
)
from resale_price_agent.seed_list import SEED_ITEMS


def _get_owner():
    return os.environ.get("POLLER_OWNER", "").strip() or None


def cmd_add(args, engine):
    owner = _get_owner()
    if owner is None:
        print(
            "Error: POLLER_OWNER is not set. Set it in .env to mark "
            "items as personal.",
            file=sys.stderr,
        )
        sys.exit(1)

    item, created, claimed = get_or_create_tracked_item(
        engine, args.query, owner=owner,
    )
    if created:
        print(f"Added item #{item['id']}: \"{item['display_name']}\"")
    elif claimed:
        print(
            f"Claiming existing item #{item['id']} as personal "
            f"(was public-only): \"{item['display_name']}\""
        )
    else:
        print(f"Already tracking item #{item['id']}: \"{item['display_name']}\"")




def cmd_list(args, engine):
    items = get_all_tracked_items(engine)
    if not items:
        print("No tracked items.")
        return
    for item in items:
        tags = []
        if item["is_seeded"]:
            tags.append("seeded")
        if item.get("owner"):
            tags.append(f"owner={item['owner']}")
        if item.get("category"):
            tags.append(item["category"])
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        date = str(item["created_at"])[:10]
        print(
            f"  #{item['id']}  [{item['status']}]  "
            f"\"{item['display_name']}\"{tag_str}  (added {date})"
        )


def cmd_status(args, engine):
    if not get_tracked_item(engine, args.id):
        print(f"Item #{args.id} not found.")
        sys.exit(1)
    set_tracked_item_status(engine, args.id, args.status)
    print(f"Set item #{args.id} status to '{args.status}'.")


def cmd_purge(args, engine):
    """Delete tracked items (and their data) not in the current seed list."""
    from resale_price_agent.db import normalize_query
    from sqlalchemy import text

    seed_queries = {normalize_query(e["query"]) for e in SEED_ITEMS}
    items = get_all_tracked_items(engine)
    to_delete = [i for i in items if i["normalized_query"] not in seed_queries]

    if not to_delete:
        print("Nothing to purge — all items match current seed list.")
        return

    print(f"Will delete {len(to_delete)} item(s) not in seed list:")
    for item in to_delete:
        print(f"  #{item['id']}  \"{item['display_name']}\"")

    if not args.yes:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    with engine.begin() as conn:
        for item in to_delete:
            # Delete dependent rows first (snapshots, decisions, alerts, recommendations)
            for table_name in ("recommendations", "decisions", "price_snapshots", "alerts"):
                try:
                    conn.execute(
                        text(f"DELETE FROM {table_name} WHERE tracked_item_id = :id"),
                        {"id": item["id"]},
                    )
                except Exception:
                    pass  # Table may not exist in all environments
            conn.execute(
                text("DELETE FROM tracked_items WHERE id = :id"),
                {"id": item["id"]},
            )

    print(f"Purged {len(to_delete)} item(s).")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage tracked items for the Pokemon card price tracker."
    )
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new item to track")
    add_p.add_argument("query", help="eBay search query")

    sub.add_parser("list", help="List all tracked items")

    status_p = sub.add_parser("status", help="Set item status")
    status_p.add_argument("id", type=int, help="Item ID")
    status_p.add_argument("status", choices=["collecting", "active"],
                          help="New status")

    purge_p = sub.add_parser("purge", help="Delete items not in current seed list")
    purge_p.add_argument("-y", "--yes", action="store_true",
                         help="Skip confirmation prompt")

    return parser


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "status": cmd_status,
    "purge": cmd_purge,
}


def main(argv=None, engine=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if engine is None:
        engine = get_engine()

    COMMANDS[args.command](args, engine)


if __name__ == "__main__":
    main()

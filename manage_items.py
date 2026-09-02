"""CLI for managing tracked items in the resale price agent watchlist."""

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
    set_tracked_item_status,
)


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


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage tracked items for the resale price agent."
    )
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new item to track")
    add_p.add_argument("query", help="eBay search query")

    sub.add_parser("list", help="List all tracked items")

    status_p = sub.add_parser("status", help="Set item status")
    status_p.add_argument("id", type=int, help="Item ID")
    status_p.add_argument("status", choices=["collecting", "active"],
                          help="New status")

    return parser


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "status": cmd_status,
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

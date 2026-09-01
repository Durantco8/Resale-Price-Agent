"""CLI for managing tracked items in the resale price agent watchlist."""

import argparse
import sys

from resale_price_agent.db import (
    add_tracked_item,
    get_all_tracked_items,
    get_engine,
    get_tracked_item,
    remove_tracked_item,
    set_tracked_item_active,
)


def cmd_add(args, engine):
    item_id = add_tracked_item(
        engine, args.query, target_price=args.target_price
    )
    price_note = f" (target: ${args.target_price:.2f})" if args.target_price else ""
    print(f"Added item #{item_id}: \"{args.query}\"{price_note}")


def cmd_list(args, engine):
    items = get_all_tracked_items(engine)
    if not items:
        print("No tracked items.")
        return
    for item in items:
        status = "active" if item["active"] else "paused"
        target = f"  target=${item['target_price']:.2f}" if item["target_price"] else ""
        date = str(item["date_added"])[:10]
        print(f"  #{item['id']}  [{status}]  \"{item['search_query']}\"{target}  (added {date})")


def cmd_pause(args, engine):
    if not get_tracked_item(engine, args.id):
        print(f"Item #{args.id} not found.")
        sys.exit(1)
    set_tracked_item_active(engine, args.id, False)
    print(f"Paused item #{args.id}.")


def cmd_resume(args, engine):
    if not get_tracked_item(engine, args.id):
        print(f"Item #{args.id} not found.")
        sys.exit(1)
    set_tracked_item_active(engine, args.id, True)
    print(f"Resumed item #{args.id}.")


def cmd_remove(args, engine):
    if not get_tracked_item(engine, args.id):
        print(f"Item #{args.id} not found.")
        sys.exit(1)
    remove_tracked_item(engine, args.id)
    print(f"Removed item #{args.id}.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage tracked items for the resale price agent."
    )
    sub = parser.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new item to track")
    add_p.add_argument("query", help="eBay search query")
    add_p.add_argument(
        "--target-price", type=float, default=None, help="Optional target price"
    )

    sub.add_parser("list", help="List all tracked items")

    pause_p = sub.add_parser("pause", help="Pause tracking for an item")
    pause_p.add_argument("id", type=int, help="Item ID to pause")

    resume_p = sub.add_parser("resume", help="Resume tracking for an item")
    resume_p.add_argument("id", type=int, help="Item ID to resume")

    remove_p = sub.add_parser("remove", help="Remove a tracked item")
    remove_p.add_argument("id", type=int, help="Item ID to remove")

    return parser


COMMANDS = {
    "add": cmd_add,
    "list": cmd_list,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "remove": cmd_remove,
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

"""Seed realistic fake listing snapshots for testing the full pipeline.

Inserts several days of price history for a tracked item with a
believable trend: prices start around $225, drift down over time
with some noise, and the final batch includes listings below the
$200 target price and well below the rolling average.

Usage:
    python seed_fake_data.py [--item-id 1]
"""

import argparse
import random

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, timezone

from resale_price_agent.db import get_engine, get_tracked_item, insert_snapshots

random.seed(42)  # reproducible

SELLERS = [
    ("sneaker_vault_pdx", 4521, "Portland, OR, US"),
    ("kicks_n_more", 892, "Los Angeles, CA, US"),
    ("sole_collector_atl", 2103, "Atlanta, GA, US"),
    ("j4_deals", 337, "Houston, TX, US"),
    ("stadium_goods_ny", 15420, "New York, NY, US"),
    ("retro_heat_chi", 1876, "Chicago, IL, US"),
]


def _make_snapshot(day_offset, base_price, idx):
    """Build a single snapshot dict at a given day offset from now."""
    seller = random.choice(SELLERS)
    noise = random.uniform(-8, 8)
    price = round(base_price + noise, 2)
    shipping = random.choice([0.0, 9.95, 14.95, None])
    condition = random.choice([
        "New with box", "New with box", "New with box",  # most common
        "New without box", "Pre-owned - Excellent",
    ])
    fmt = random.choice(["FIXED_PRICE", "FIXED_PRICE", "FIXED_PRICE", "AUCTION"])

    return {
        "ebay_item_id": f"v1|fake{day_offset:02d}{idx:02d}|0",
        "title": f"Jordan 4 Retro Military Black - Size 10 {'DS' if 'New' in condition else ''}".strip(),
        "price": price,
        "currency": "USD",
        "condition": condition,
        "seller_feedback_score": seller[1],
        "shipping_cost": shipping,
        "item_location": seller[2],
        "buying_format": fmt,
        "item_url": f"https://www.ebay.com/itm/fake{day_offset:02d}{idx:02d}",
        "snapshot_time": datetime.now(timezone.utc) - timedelta(days=day_offset, hours=random.randint(0, 12)),
    }


def seed(engine, item_id):
    item = get_tracked_item(engine, item_id)
    if not item:
        print(f"Error: tracked item #{item_id} not found. Add one first:")
        print(f'  python manage_items.py add "Jordan 4 Retro Military Black size 10" --target-price 200')
        return

    print(f"Seeding fake data for item #{item_id}: \"{item['search_query']}\"")

    # --- Days 14-10: Stable around $225 ---
    for day in range(14, 10, -1):
        snaps = [_make_snapshot(day, 225, i) for i in range(random.randint(3, 6))]
        insert_snapshots(engine, item_id, snaps)
        print(f"  Day -{day:2d}: {len(snaps)} listings, avg ~$225")

    # --- Days 9-5: Drifting down to $215 ---
    for day in range(9, 5, -1):
        base = 225 - (10 - day) * 2  # 223, 221, 219, 217
        snaps = [_make_snapshot(day, base, i) for i in range(random.randint(4, 7))]
        insert_snapshots(engine, item_id, snaps)
        print(f"  Day -{day:2d}: {len(snaps)} listings, avg ~${base}")

    # --- Days 4-2: Down to $210 with increasing supply ---
    for day in range(4, 1, -1):
        base = 215 - (5 - day) * 3  # 212, 209, 206
        snaps = [_make_snapshot(day, base, i) for i in range(random.randint(5, 9))]
        insert_snapshots(engine, item_id, snaps)
        print(f"  Day -{day:2d}: {len(snaps)} listings, avg ~${base}")

    # --- Today: The drop — some listings below $200 target ---
    today_snaps = [
        {
            "ebay_item_id": "v1|drop01|0",
            "title": "Jordan 4 Retro Military Black - Size 10 DS",
            "price": 192.00,
            "currency": "USD",
            "condition": "New with box",
            "seller_feedback_score": 2103,
            "shipping_cost": 0.0,
            "item_location": "Atlanta, GA, US",
            "buying_format": "FIXED_PRICE",
            "item_url": "https://www.ebay.com/itm/drop01",
            "snapshot_time": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        {
            "ebay_item_id": "v1|drop02|0",
            "title": "Air Jordan 4 Military Black Mens 10 VNDS",
            "price": 189.99,
            "currency": "USD",
            "condition": "New with box",
            "seller_feedback_score": 15420,
            "shipping_cost": 14.95,
            "item_location": "New York, NY, US",
            "buying_format": "FIXED_PRICE",
            "item_url": "https://www.ebay.com/itm/drop02",
            "snapshot_time": datetime.now(timezone.utc) - timedelta(minutes=30),
        },
        {
            "ebay_item_id": "v1|drop03|0",
            "title": "Jordan 4 Military Black Size 10 Brand New",
            "price": 208.50,
            "currency": "USD",
            "condition": "New with box",
            "seller_feedback_score": 892,
            "shipping_cost": 9.95,
            "item_location": "Los Angeles, CA, US",
            "buying_format": "FIXED_PRICE",
            "item_url": "https://www.ebay.com/itm/drop03",
            "snapshot_time": datetime.now(timezone.utc) - timedelta(minutes=15),
        },
    ]
    insert_snapshots(engine, item_id, today_snaps)
    print(f"  Today:   3 listings — $192.00, $189.99, $208.50 (two below $200 target)")

    print(f"\nDone. Seeded ~{14 * 5 + 3} snapshots across 14 days.")
    print("Now run:  python poller.py --skip-ebay")


def main():
    parser = argparse.ArgumentParser(description="Seed fake listing data for testing.")
    parser.add_argument("--item-id", type=int, default=1, help="Tracked item ID to seed (default: 1)")
    args = parser.parse_args()

    engine = get_engine()
    seed(engine, args.item_id)


if __name__ == "__main__":
    main()

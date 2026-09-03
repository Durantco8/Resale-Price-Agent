"""Dev runner: Flask backend with mock eBay/LLM/email clients.

Usage:
    python dev_server.py              # start Flask on port 5000
    python dev_server.py --poll N     # run N poll cycles, then start Flask
    python dev_server.py --poll-only N  # run N poll cycles, then exit (no Flask)

All data lives in an in-memory SQLite database — nothing persists between runs.
Zero network calls. No env vars needed.
"""

import argparse
import json
import random
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from resale_price_agent.app import create_app
from resale_price_agent.db import metadata
from resale_price_agent.ebay_client import ListingSnapshot
from resale_price_agent.poller import poll_all_items
from resale_price_agent.seed_list import seed_all


# ---------------------------------------------------------------------------
# Mock clients
# ---------------------------------------------------------------------------

class MockEbayClient:
    """Returns 2-4 fake listings per query with slightly randomized prices."""

    def search_listings(self, query, limit=50):
        base = hash(query) % 200 + 50  # deterministic base price per query
        count = random.randint(2, 4)
        now = datetime.now(timezone.utc).isoformat()
        return [
            ListingSnapshot(
                item_id=f"v1|{abs(hash(query + str(i))) % 900000000000 + 100000000000}|0",
                title=f"{query} - Listing {i + 1}",
                price_amount=round(base + random.uniform(-20, 20), 2),
                price_currency="USD",
                condition=random.choice(["New", "New with box", "Pre-owned"]),
                seller_feedback_score=random.randint(50, 5000),
                item_url=f"https://www.ebay.com/itm/{abs(hash(query + str(i))) % 900000000000 + 100000000000}",
                shipping_cost=round(random.uniform(0, 12), 2),
                item_location="New York, NY, US",
                buying_options=["FIXED_PRICE"],
                snapshot_time=now,
            )
            for i in range(count)
        ]


class MockLLMClient:
    """Returns a random buy/wait/skip decision with reasoning."""

    def __init__(self):
        self.models = self

    def generate_content(self, **kwargs):
        action = random.choice(["buy_now", "wait", "wait", "skip"])
        resp = {
            "action": action,
            "confidence": round(random.uniform(0.5, 0.95), 2),
            "reasoning": {
                "buy_now": "Prices are below historical average — good time to buy.",
                "wait": "Prices are stable. No urgency to purchase right now.",
                "skip": "Prices are elevated above typical range. Better deals likely ahead.",
            }[action],
        }

        class _Response:
            text = json.dumps(resp)

        return _Response()


def mock_send_email(to, subject, body):
    print(f"  [MOCK EMAIL] To: {to} | Subject: {subject}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Dev server with mock clients")
    parser.add_argument("--poll", type=int, default=0,
                        help="Run N poll cycles before starting Flask")
    parser.add_argument("--poll-only", type=int, default=0,
                        help="Run N poll cycles then exit (no Flask)")
    args = parser.parse_args()

    cycles = args.poll or args.poll_only

    # --- Engine + tables + seed data ---
    engine = create_engine(
        "sqlite:///:memory:", echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    result = seed_all(engine)
    print(f"Seeded: {result['created']} created, {result['existing']} existing")

    # --- Poll cycles ---
    ebay = MockEbayClient()
    llm = MockLLMClient()

    for i in range(cycles):
        print(f"\n--- Poll cycle {i + 1}/{cycles} ---")
        summary = poll_all_items(engine, ebay, llm_client=llm, send_fn=mock_send_email)
        print(f"  processed={summary['processed']}, "
              f"snapshots={summary['total_snapshots']}, "
              f"alerts={summary['alerts_sent']}")

    if args.poll_only:
        print("\nDone (--poll-only). Exiting.")
        return

    # --- Flask ---
    app = create_app(config={
        "ENGINE": engine,
        "SEARCH_RATE_LIMIT": "100/minute",
        "ALERT_RATE_LIMIT": "100/minute",
    })
    print(f"\nStarting Flask on http://localhost:5001")
    print("Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()

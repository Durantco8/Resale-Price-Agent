"""CLI entry point — runs the unified polling pipeline."""

import argparse
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from resale_price_agent.db import get_engine
from resale_price_agent.ebay_client import EbayClient
from resale_price_agent.notifier import send_email
from resale_price_agent.poller import poll_all_items

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

    poll_all_items(
        engine=get_engine(),
        ebay_client=None if args.skip_ebay else EbayClient(),
        send_fn=send_email,
        notify_send_fn=send_email,
        notify_recipient=os.environ.get("NOTIFY_TO", ""),
        skip_ebay=args.skip_ebay,
    )


if __name__ == "__main__":
    main()

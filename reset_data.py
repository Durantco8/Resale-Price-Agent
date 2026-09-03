"""Safely reset trend data while preserving tracked-item configuration.

Running without ``--confirm`` prints an exact preview and makes no changes::

    python reset_data.py

Pass ``--confirm`` only after reviewing that preview::

    python reset_data.py --confirm
"""

import argparse
import sys

from dotenv import load_dotenv
from sqlalchemy import func, select

load_dotenv()

from resale_price_agent.db import (  # noqa: E402
    alerts,
    decisions,
    get_engine,
    snapshots,
    tracked_items,
)


class ResetConfirmationRequired(RuntimeError):
    """Raised when a reset is requested without explicit confirmation."""


def get_reset_counts(engine) -> dict[str, int]:
    """Return exact counts for the rows affected or preserved by a reset."""
    with engine.connect() as conn:
        return {
            "snapshots": conn.scalar(select(func.count()).select_from(snapshots)),
            "decisions": conn.scalar(select(func.count()).select_from(decisions)),
            "tracked_items": conn.scalar(
                select(func.count()).select_from(tracked_items)
            ),
            "statuses_to_reset": conn.scalar(
                select(func.count())
                .select_from(tracked_items)
                .where(tracked_items.c.status != "collecting")
            ),
            "alerts": conn.scalar(select(func.count()).select_from(alerts)),
        }


def report_reset_preview(counts: dict[str, int]) -> None:
    """Print the exact scope of a prospective reset."""
    print("Reset preview (no changes made yet):")
    print(f"  Snapshots to delete: {counts['snapshots']}")
    print(f"  Decisions to delete: {counts['decisions']}")
    print(f"  Tracked items to preserve: {counts['tracked_items']}")
    print(f"  Item statuses to reset to collecting: {counts['statuses_to_reset']}")
    print(f"  Alerts to preserve: {counts['alerts']}")


def reset(engine, *, confirmed: bool = False) -> dict[str, int]:
    """Reset snapshots, decisions, and item statuses after confirmation.

    The preview is always printed before any write occurs. Tracked-item rows
    and their configuration, including ownership, seed flags, and eBay
    category IDs, are preserved. Alert subscriptions are also untouched.
    """
    counts = get_reset_counts(engine)
    report_reset_preview(counts)

    if not confirmed:
        raise ResetConfirmationRequired(
            "Explicit confirmation is required; no data was changed."
        )

    with engine.begin() as conn:
        decisions_result = conn.execute(decisions.delete())
        snapshots_result = conn.execute(snapshots.delete())
        statuses_result = conn.execute(
            tracked_items.update()
            .where(tracked_items.c.status != "collecting")
            .values(status="collecting")
        )

    result = {
        **counts,
        "deleted_snapshots": snapshots_result.rowcount,
        "deleted_decisions": decisions_result.rowcount,
        "reset_statuses": statuses_result.rowcount,
    }
    print(
        f"Reset complete: deleted {result['deleted_snapshots']} snapshot(s) "
        f"and {result['deleted_decisions']} decision(s); reset "
        f"{result['reset_statuses']} item status(es) to collecting."
    )
    print(
        f"Preserved {counts['tracked_items']} tracked item(s) and "
        f"{counts['alerts']} alert(s)."
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Clear snapshots and decisions and reset tracked-item statuses. "
            "Tracked items and alerts are preserved."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicitly authorize the reset after reviewing the row-count preview.",
    )
    args = parser.parse_args()

    try:
        reset(get_engine(), confirmed=args.confirm)
    except ResetConfirmationRequired as exc:
        print(f"\n{exc}")
        print("Review the counts above, then rerun with --confirm to execute.")
        sys.exit(1)


if __name__ == "__main__":
    main()

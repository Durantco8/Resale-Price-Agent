"""Public search logic — find-or-create a tracked item and return its data.

This is the core data layer for the search endpoint.  It stays decoupled
from any web framework so it can be tested with an in-memory SQLite engine
and later wrapped by a thin Flask route handler.
"""

from resale_price_agent.db import (
    get_decisions_for_item,
    get_or_create_tracked_item,
    get_snapshots_for_item,
)


def search(engine, raw_query: str) -> dict:
    """Look up (or create) a tracked item and return its current state.

    Returns a dict with:
        tracked_item  — the full tracked_item row
        created       — True if this search created a new row
        snapshots     — list of snapshot dicts (newest first)
        decisions     — list of decision dicts (newest first)
        snapshot_count — total snapshots available
        status        — the item's current status ("collecting" or "active")
    """
    item, created, _ = get_or_create_tracked_item(engine, raw_query)
    item_id = item["id"]

    item_snapshots = get_snapshots_for_item(engine, item_id)
    item_decisions = get_decisions_for_item(engine, item_id)

    return {
        "tracked_item": item,
        "created": created,
        "snapshots": item_snapshots,
        "decisions": item_decisions,
        "snapshot_count": len(item_snapshots),
        "status": item["status"],
    }

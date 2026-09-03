"""Safety and preservation tests for the reset utility."""

import pytest
from sqlalchemy import func, select

from reset_data import ResetConfirmationRequired, get_reset_counts, reset
from resale_price_agent.db import (
    alerts,
    create_alert,
    decisions,
    get_or_create_tracked_item,
    get_tracked_item,
    insert_decision,
    insert_snapshots,
    seed_tracked_item,
    set_tracked_item_status,
    snapshots,
)


def _populate_reset_fixture(engine):
    personal, _, _ = get_or_create_tracked_item(
        engine, "Jordan 4 size 10", owner="durantco"
    )
    seeded, _ = seed_tracked_item(
        engine,
        "PlayStation 5 Console",
        display_name="PS5",
        ebay_category_id="139971",
    )
    set_tracked_item_status(engine, personal["id"], "active")
    set_tracked_item_status(engine, seeded["id"], "active")

    for item in (personal, seeded):
        insert_snapshots(
            engine,
            item["id"],
            [
                {
                    "ebay_item_id": f"item-{item['id']}",
                    "title": "Listing",
                    "price": 100,
                }
            ],
        )
        insert_decision(engine, item["id"], "llm_reasoning", action="wait")

    alert = create_alert(engine, "buyer@example.com", seeded["id"], "buy_now")
    return personal, seeded, alert


def _table_count(engine, table) -> int:
    with engine.connect() as conn:
        return conn.scalar(select(func.count()).select_from(table))


def test_reset_requires_confirmation_and_reports_exact_preview(engine, capsys):
    _populate_reset_fixture(engine)

    with pytest.raises(ResetConfirmationRequired, match="no data was changed"):
        reset(engine)

    output = capsys.readouterr().out
    assert "Snapshots to delete: 2" in output
    assert "Decisions to delete: 2" in output
    assert "Tracked items to preserve: 2" in output
    assert "Item statuses to reset to collecting: 2" in output
    assert "Alerts to preserve: 1" in output
    assert _table_count(engine, snapshots) == 2
    assert _table_count(engine, decisions) == 2


def test_confirmed_reset_preserves_items_configuration_and_alerts(engine, capsys):
    personal, seeded, alert = _populate_reset_fixture(engine)

    result = reset(engine, confirmed=True)

    output = capsys.readouterr().out
    assert output.index("Snapshots to delete: 2") < output.index("Reset complete:")
    assert result["deleted_snapshots"] == 2
    assert result["deleted_decisions"] == 2
    assert result["reset_statuses"] == 2
    assert _table_count(engine, snapshots) == 0
    assert _table_count(engine, decisions) == 0
    assert _table_count(engine, alerts) == 1

    personal_after = get_tracked_item(engine, personal["id"])
    seeded_after = get_tracked_item(engine, seeded["id"])
    assert personal_after["status"] == "collecting"
    assert personal_after["owner"] == "durantco"
    assert personal_after["is_seeded"] is False
    assert personal_after["search_query"] == "Jordan 4 size 10"
    assert seeded_after["status"] == "collecting"
    assert seeded_after["is_seeded"] is True
    assert seeded_after["ebay_category_id"] == "139971"
    assert seeded_after["display_name"] == "PS5"

    with engine.connect() as conn:
        preserved_alert = conn.execute(
            alerts.select().where(alerts.c.id == alert["id"])
        ).one()
    assert preserved_alert.email == "buyer@example.com"
    assert preserved_alert.active is True


def test_get_reset_counts_includes_already_collecting_items(engine):
    get_or_create_tracked_item(engine, "Newly tracked item")

    assert get_reset_counts(engine) == {
        "snapshots": 0,
        "decisions": 0,
        "tracked_items": 1,
        "statuses_to_reset": 0,
        "alerts": 0,
    }

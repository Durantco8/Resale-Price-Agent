"""Tests for the storage layer — all use in-memory SQLite, no disk I/O."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import (
    add_tracked_item,
    get_active_tracked_items,
    get_decisions_for_item,
    get_snapshots_for_item,
    get_tracked_item,
    insert_decision,
    insert_snapshots,
    metadata,
    remove_tracked_item,
    set_tracked_item_active,
    update_decision_outcome,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# Tracked items
# ---------------------------------------------------------------------------

class TestTrackedItems:
    def test_add_and_get(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4 Military Black size 10")
        item = get_tracked_item(engine, item_id)

        assert item is not None
        assert item["search_query"] == "Jordan 4 Military Black size 10"
        assert item["active"] is True
        assert item["target_price"] is None
        assert item["date_added"] is not None

    def test_add_with_target_price(self, engine):
        item_id = add_tracked_item(
            engine, "Yeezy 350 size 11", target_price=180.0
        )
        item = get_tracked_item(engine, item_id)

        assert item["target_price"] == 180.0

    def test_get_nonexistent_returns_none(self, engine):
        assert get_tracked_item(engine, 9999) is None

    def test_get_active_items(self, engine):
        add_tracked_item(engine, "Item A")
        id_b = add_tracked_item(engine, "Item B")
        add_tracked_item(engine, "Item C")

        set_tracked_item_active(engine, id_b, False)
        active = get_active_tracked_items(engine)

        queries = [i["search_query"] for i in active]
        assert "Item A" in queries
        assert "Item C" in queries
        assert "Item B" not in queries

    def test_pause_and_resume(self, engine):
        item_id = add_tracked_item(engine, "Item X")
        assert get_tracked_item(engine, item_id)["active"] is True

        set_tracked_item_active(engine, item_id, False)
        assert get_tracked_item(engine, item_id)["active"] is False

        set_tracked_item_active(engine, item_id, True)
        assert get_tracked_item(engine, item_id)["active"] is True

    def test_pause_nonexistent_returns_false(self, engine):
        assert set_tracked_item_active(engine, 9999, False) is False

    def test_remove(self, engine):
        item_id = add_tracked_item(engine, "Item to remove")
        assert remove_tracked_item(engine, item_id) is True
        assert get_tracked_item(engine, item_id) is None

    def test_remove_nonexistent_returns_false(self, engine):
        assert remove_tracked_item(engine, 9999) is False

    def test_auto_increment_ids(self, engine):
        id1 = add_tracked_item(engine, "First")
        id2 = add_tracked_item(engine, "Second")
        assert id2 > id1


# ---------------------------------------------------------------------------
# Listing snapshots
# ---------------------------------------------------------------------------

class TestListingSnapshots:
    def _sample_snapshots(self):
        return [
            {
                "ebay_item_id": "v1|111|0",
                "title": "Jordan 4 Military Black",
                "price": 219.99,
                "currency": "USD",
                "condition": "New with box",
                "seller_feedback_score": 5432,
                "shipping_cost": 14.95,
                "item_location": "Portland, OR, US",
                "buying_format": "FIXED_PRICE",
                "item_url": "https://www.ebay.com/itm/111",
                "snapshot_time": datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
            },
            {
                "ebay_item_id": "v1|222|0",
                "title": "Air Jordan 4 Military Black",
                "price": 205.00,
                "condition": "New with box",
                "buying_format": "AUCTION",
                "snapshot_time": datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
            },
        ]

    def test_insert_and_retrieve(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        count = insert_snapshots(engine, item_id, self._sample_snapshots())

        assert count == 2
        rows = get_snapshots_for_item(engine, item_id)
        assert len(rows) == 2

    def test_fields_stored_correctly(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        insert_snapshots(engine, item_id, self._sample_snapshots())
        rows = get_snapshots_for_item(engine, item_id)

        # Rows are ordered by snapshot_time desc; both have the same time
        ebay_ids = {r["ebay_item_id"] for r in rows}
        assert "v1|111|0" in ebay_ids
        assert "v1|222|0" in ebay_ids

        first = next(r for r in rows if r["ebay_item_id"] == "v1|111|0")
        assert first["price"] == 219.99
        assert first["shipping_cost"] == 14.95
        assert first["item_location"] == "Portland, OR, US"
        assert first["buying_format"] == "FIXED_PRICE"

    def test_nullable_fields_default_to_none(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        insert_snapshots(engine, item_id, self._sample_snapshots())
        rows = get_snapshots_for_item(engine, item_id)

        second = next(r for r in rows if r["ebay_item_id"] == "v1|222|0")
        assert second["shipping_cost"] is None
        assert second["item_location"] is None
        assert second["seller_feedback_score"] is None

    def test_limit(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        insert_snapshots(engine, item_id, self._sample_snapshots())
        rows = get_snapshots_for_item(engine, item_id, limit=1)
        assert len(rows) == 1

    def test_empty_list_inserts_nothing(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        count = insert_snapshots(engine, item_id, [])
        assert count == 0
        assert get_snapshots_for_item(engine, item_id) == []

    def test_snapshots_isolated_by_tracked_item(self, engine):
        id_a = add_tracked_item(engine, "Item A")
        id_b = add_tracked_item(engine, "Item B")
        insert_snapshots(engine, id_a, self._sample_snapshots())
        insert_snapshots(
            engine,
            id_b,
            [
                {
                    "ebay_item_id": "v1|333|0",
                    "title": "Other item",
                    "price": 99.0,
                    "snapshot_time": datetime(2026, 8, 31, tzinfo=timezone.utc),
                }
            ],
        )

        assert len(get_snapshots_for_item(engine, id_a)) == 2
        assert len(get_snapshots_for_item(engine, id_b)) == 1

    def test_fk_constraint(self, engine):
        """Inserting a snapshot for a nonexistent tracked item should fail."""
        # SQLite doesn't enforce FKs by default; enable them
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_fk_pragma(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        # Need a fresh connection after adding the listener
        eng2 = create_engine("sqlite:///:memory:", echo=False)

        @event.listens_for(eng2, "connect")
        def _set_fk_pragma2(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        metadata.create_all(eng2)

        with pytest.raises(Exception):
            insert_snapshots(
                eng2,
                9999,
                [
                    {
                        "ebay_item_id": "v1|000|0",
                        "title": "Orphan",
                        "price": 50.0,
                        "snapshot_time": datetime(2026, 8, 30, tzinfo=timezone.utc),
                    }
                ],
            )


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class TestDecisions:
    def test_insert_price_drop_alert(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        dec_id = insert_decision(
            engine,
            item_id,
            "price_drop_alert",
            computed_signals=json.dumps({"avg_price": 220.0, "drop_pct": 12.5}),
            reasoning="15% below rolling average",
        )

        rows = get_decisions_for_item(engine, item_id)
        assert len(rows) == 1
        assert rows[0]["id"] == dec_id
        assert rows[0]["event_type"] == "price_drop_alert"
        assert rows[0]["action"] is None
        assert rows[0]["confidence"] is None
        assert rows[0]["reasoning"] == "15% below rolling average"
        assert rows[0]["outcome"] is None

    def test_insert_llm_reasoning(self, engine):
        item_id = add_tracked_item(engine, "Yeezy 350")
        insert_decision(
            engine,
            item_id,
            "llm_reasoning",
            computed_signals=json.dumps({"avg_price": 180.0, "trend": "down"}),
            action="buy_now",
            confidence=0.85,
            reasoning="Prices trending down with high inventory",
        )

        rows = get_decisions_for_item(engine, item_id)
        assert rows[0]["action"] == "buy_now"
        assert rows[0]["confidence"] == 0.85

    def test_update_outcome(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        dec_id = insert_decision(engine, item_id, "price_drop_alert")

        assert update_decision_outcome(engine, dec_id, "price_went_lower") is True
        rows = get_decisions_for_item(engine, item_id)
        assert rows[0]["outcome"] == "price_went_lower"

    def test_update_outcome_nonexistent(self, engine):
        assert update_decision_outcome(engine, 9999, "anything") is False

    def test_decisions_isolated_by_tracked_item(self, engine):
        id_a = add_tracked_item(engine, "Item A")
        id_b = add_tracked_item(engine, "Item B")
        insert_decision(engine, id_a, "price_drop_alert")
        insert_decision(engine, id_a, "llm_reasoning", action="wait")
        insert_decision(engine, id_b, "price_drop_alert")

        assert len(get_decisions_for_item(engine, id_a)) == 2
        assert len(get_decisions_for_item(engine, id_b)) == 1

    def test_limit(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        insert_decision(engine, item_id, "price_drop_alert")
        insert_decision(engine, item_id, "llm_reasoning")
        insert_decision(engine, item_id, "price_drop_alert")

        rows = get_decisions_for_item(engine, item_id, limit=2)
        assert len(rows) == 2

    def test_timestamp_auto_populated(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        insert_decision(engine, item_id, "price_drop_alert")

        rows = get_decisions_for_item(engine, item_id)
        assert rows[0]["timestamp"] is not None

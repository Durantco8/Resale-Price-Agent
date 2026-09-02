"""Tests for the storage layer — schema, dedupe, CRUD, alerts."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import (
    create_alert,
    get_active_alerts_for_item,
    get_all_tracked_items,
    get_decisions_for_item,
    get_or_create_tracked_item,
    get_seeded_items,
    get_snapshots_for_item,
    get_tracked_item,
    get_tracked_item_by_query,
    insert_decision,
    insert_snapshots,
    metadata,
    normalize_query,
    seed_tracked_item,
    set_tracked_item_status,
    unsubscribe_by_token,
)


# ---------------------------------------------------------------------------
# Query normalization
# ---------------------------------------------------------------------------

class TestNormalizeQuery:
    def test_lowercases(self):
        assert normalize_query("Jordan 4 Retro") == "jordan 4 retro"

    def test_collapses_whitespace(self):
        assert normalize_query("jordan   4    retro") == "jordan 4 retro"

    def test_strips_leading_trailing(self):
        assert normalize_query("  jordan 4  ") == "jordan 4"

    def test_tabs_and_newlines(self):
        assert normalize_query("jordan\t4\nretro") == "jordan 4 retro"

    def test_already_normalized(self):
        assert normalize_query("jordan 4") == "jordan 4"

    def test_empty_after_strip(self):
        assert normalize_query("   ") == ""


# ---------------------------------------------------------------------------
# Dedupe — get_or_create_tracked_item
# ---------------------------------------------------------------------------

class TestDedupe:
    def test_creates_new_item(self, engine):
        item, created, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        assert created is True
        assert item["search_query"] == "Jordan 4 Retro"
        assert item["normalized_query"] == "jordan 4 retro"
        assert item["status"] == "collecting"
        assert item["is_seeded"] is False

    def test_same_query_returns_existing(self, engine):
        item1, c1, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        item2, c2, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        assert c1 is True
        assert c2 is False
        assert item1["id"] == item2["id"]

    def test_different_casing_dedupes(self, engine):
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        item2, c2, _ = get_or_create_tracked_item(engine, "jordan 4 retro")
        assert c2 is False
        assert item1["id"] == item2["id"]

    def test_different_whitespace_dedupes(self, engine):
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        item2, c2, _ = get_or_create_tracked_item(engine, "  Jordan   4  Retro  ")
        assert c2 is False
        assert item1["id"] == item2["id"]

    def test_different_items_get_separate_rows(self, engine):
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        item2, c2, _ = get_or_create_tracked_item(engine, "Nike Dunk Low")
        assert c2 is True
        assert item1["id"] != item2["id"]

    def test_empty_query_raises(self, engine):
        with pytest.raises(ValueError, match="empty"):
            get_or_create_tracked_item(engine, "   ")

    def test_only_one_row_in_db(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4")
        get_or_create_tracked_item(engine, "jordan 4")
        get_or_create_tracked_item(engine, "  JORDAN   4  ")
        assert len(get_all_tracked_items(engine)) == 1


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class TestOwnership:
    def test_create_with_owner(self, engine):
        item, created, _ = get_or_create_tracked_item(engine, "Jordan 4", owner="durantco")
        assert created
        assert item["owner"] == "durantco"

    def test_create_without_owner(self, engine):
        item, created, _ = get_or_create_tracked_item(engine, "Jordan 4")
        assert created
        assert item["owner"] is None

    def test_claim_existing_unowned_item(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4")  # public search
        item, created, claimed = get_or_create_tracked_item(engine, "Jordan 4", owner="durantco")
        assert not created
        assert claimed
        assert item["owner"] == "durantco"

    def test_claim_already_owned_is_noop(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4", owner="durantco")
        item, created, claimed = get_or_create_tracked_item(engine, "Jordan 4", owner="someone_else")
        assert not created
        assert not claimed
        assert item["owner"] == "durantco"

    def test_no_owner_does_not_overwrite_existing(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4", owner="durantco")
        item, created, claimed = get_or_create_tracked_item(engine, "Jordan 4")
        assert not created
        assert not claimed
        assert item["owner"] == "durantco"


# ---------------------------------------------------------------------------
# Seeded items
# ---------------------------------------------------------------------------

class TestSeededItems:
    def test_seed_creates_with_flag(self, engine):
        item, created = seed_tracked_item(engine, "PS5 Console")
        assert created is True
        assert item["is_seeded"] is True
        assert item["status"] == "collecting"

    def test_seed_custom_display_name(self, engine):
        item, _ = seed_tracked_item(
            engine, "ps5 console", display_name="PlayStation 5 Console"
        )
        assert item["display_name"] == "PlayStation 5 Console"

    def test_seed_dedupes_against_existing(self, engine):
        item1, _ = seed_tracked_item(engine, "PS5 Console")
        item2, c2 = seed_tracked_item(engine, "ps5 console")
        assert c2 is False
        assert item1["id"] == item2["id"]

    def test_seed_promotes_user_created(self, engine):
        """A user-created item gets is_seeded=True if later seeded."""
        item1, _, _ = get_or_create_tracked_item(engine, "PS5 Console")
        assert item1["is_seeded"] is False

        item2, c2 = seed_tracked_item(engine, "PS5 Console")
        assert c2 is False
        assert item2["is_seeded"] is True
        assert item1["id"] == item2["id"]

        refreshed = get_tracked_item(engine, item1["id"])
        assert refreshed["is_seeded"] is True

    def test_get_seeded_items_filters(self, engine):
        seed_tracked_item(engine, "PS5 Console")
        seed_tracked_item(engine, "iPhone 15 Pro")
        get_or_create_tracked_item(engine, "random sneaker")

        seeded = get_seeded_items(engine)
        assert len(seeded) == 2
        names = {s["normalized_query"] for s in seeded}
        assert names == {"ps5 console", "iphone 15 pro"}

    def test_seed_empty_query_raises(self, engine):
        with pytest.raises(ValueError, match="empty"):
            seed_tracked_item(engine, "  ")


# ---------------------------------------------------------------------------
# Tracked items — read helpers
# ---------------------------------------------------------------------------

class TestTrackedItemReads:
    def test_get_by_id(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        fetched = get_tracked_item(engine, item["id"])
        assert fetched["search_query"] == "Jordan 4"

    def test_get_nonexistent(self, engine):
        assert get_tracked_item(engine, 999) is None

    def test_get_by_query(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4 Retro")
        fetched = get_tracked_item_by_query(engine, "  jordan   4   retro  ")
        assert fetched is not None
        assert fetched["search_query"] == "Jordan 4 Retro"

    def test_get_by_query_not_found(self, engine):
        assert get_tracked_item_by_query(engine, "nonexistent") is None

    def test_set_status(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        assert item["status"] == "collecting"

        result = set_tracked_item_status(engine, item["id"], "active")
        assert result is True

        refreshed = get_tracked_item(engine, item["id"])
        assert refreshed["status"] == "active"

    def test_set_status_nonexistent(self, engine):
        assert set_tracked_item_status(engine, 999, "active") is False


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

class TestSnapshots:
    def test_insert_and_retrieve(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        snaps = [
            {
                "ebay_item_id": "v1|111|0",
                "title": "Jordan 4 Military Black",
                "price": 200.0,
                "currency": "USD",
                "condition": "New",
            },
            {
                "ebay_item_id": "v1|222|0",
                "title": "Jordan 4 Military Black Used",
                "price": 180.0,
            },
        ]
        count = insert_snapshots(engine, item["id"], snaps)
        assert count == 2

        rows = get_snapshots_for_item(engine, item["id"])
        assert len(rows) == 2

    def test_empty_list(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        assert insert_snapshots(engine, item["id"], []) == 0

    def test_limit(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        snaps = [
            {"ebay_item_id": f"id-{i}", "title": "T", "price": 100.0 + i}
            for i in range(10)
        ]
        insert_snapshots(engine, item["id"], snaps)
        assert len(get_snapshots_for_item(engine, item["id"], limit=3)) == 3

    def test_since_filter(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        now = datetime.now(timezone.utc)
        snaps = [
            {
                "ebay_item_id": "old",
                "title": "T",
                "price": 100.0,
                "snapshot_time": now - timedelta(days=30),
            },
            {
                "ebay_item_id": "new",
                "title": "T",
                "price": 100.0,
                "snapshot_time": now - timedelta(hours=1),
            },
        ]
        insert_snapshots(engine, item["id"], snaps)
        recent = get_snapshots_for_item(
            engine, item["id"], since=now - timedelta(days=7)
        )
        assert len(recent) == 1
        assert recent[0]["ebay_item_id"] == "new"

    def test_isolated_by_tracked_item(self, engine):
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        item2, _, _ = get_or_create_tracked_item(engine, "Nike Dunk")
        insert_snapshots(engine, item1["id"], [
            {"ebay_item_id": "a", "title": "T", "price": 100.0},
        ])
        insert_snapshots(engine, item2["id"], [
            {"ebay_item_id": "b", "title": "T", "price": 200.0},
        ])
        assert len(get_snapshots_for_item(engine, item1["id"])) == 1
        assert len(get_snapshots_for_item(engine, item2["id"])) == 1


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class TestDecisions:
    def test_insert_and_retrieve(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        dec_id = insert_decision(
            engine, item["id"], "llm_reasoning",
            action="buy_now", confidence=0.85,
            reasoning="Good price", computed_signals="{}",
        )
        assert dec_id > 0

        decs = get_decisions_for_item(engine, item["id"])
        assert len(decs) == 1
        assert decs[0]["action"] == "buy_now"
        assert decs[0]["confidence"] == 0.85

    def test_limit(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        for i in range(5):
            insert_decision(engine, item["id"], "llm_reasoning", action="wait")
        assert len(get_decisions_for_item(engine, item["id"], limit=2)) == 2

    def test_isolated_by_item(self, engine):
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        item2, _, _ = get_or_create_tracked_item(engine, "Nike Dunk")
        insert_decision(engine, item1["id"], "llm_reasoning", action="wait")
        insert_decision(engine, item2["id"], "llm_reasoning", action="buy_now")
        assert len(get_decisions_for_item(engine, item1["id"])) == 1
        assert len(get_decisions_for_item(engine, item2["id"])) == 1


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_create_alert(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(
            engine, "test@example.com", item["id"], "price_below:180.00",
        )
        assert alert["email"] == "test@example.com"
        assert alert["condition"] == "price_below:180.00"
        assert alert["active"] is True
        assert len(alert["unsubscribe_token"]) == 32  # uuid4 hex

    def test_unique_tokens(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        a1 = create_alert(engine, "a@b.com", item["id"], "buy_now")
        a2 = create_alert(engine, "c@d.com", item["id"], "buy_now")
        assert a1["unsubscribe_token"] != a2["unsubscribe_token"]

    def test_get_active_alerts(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        create_alert(engine, "a@b.com", item["id"], "buy_now")
        create_alert(engine, "c@d.com", item["id"], "price_below:200")

        active = get_active_alerts_for_item(engine, item["id"])
        assert len(active) == 2

    def test_unsubscribe(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(engine, "a@b.com", item["id"], "buy_now")
        token = alert["unsubscribe_token"]

        result = unsubscribe_by_token(engine, token)
        assert result is True

        active = get_active_alerts_for_item(engine, item["id"])
        assert len(active) == 0

    def test_unsubscribe_bad_token(self, engine):
        assert unsubscribe_by_token(engine, "nonexistent") is False

    def test_multiple_alerts_same_email(self, engine):
        """Same email can subscribe to multiple items."""
        item1, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        item2, _, _ = get_or_create_tracked_item(engine, "Nike Dunk")
        create_alert(engine, "a@b.com", item1["id"], "buy_now")
        create_alert(engine, "a@b.com", item2["id"], "price_below:100")

        assert len(get_active_alerts_for_item(engine, item1["id"])) == 1
        assert len(get_active_alerts_for_item(engine, item2["id"])) == 1

    def test_unsubscribe_only_affects_target(self, engine):
        """Unsubscribing one alert doesn't deactivate others."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        a1 = create_alert(engine, "a@b.com", item["id"], "buy_now")
        create_alert(engine, "c@d.com", item["id"], "buy_now")

        unsubscribe_by_token(engine, a1["unsubscribe_token"])
        active = get_active_alerts_for_item(engine, item["id"])
        assert len(active) == 1
        assert active[0]["email"] == "c@d.com"

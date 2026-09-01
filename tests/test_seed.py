"""Tests for the seed list setup."""

import pytest

from resale_price_agent.db import get_all_tracked_items, get_seeded_items
from resale_price_agent.seed_list import SEED_ITEMS, seed_all


class TestSeedAll:
    def test_creates_all_items(self, engine):
        result = seed_all(engine)

        assert result["created"] == len(SEED_ITEMS)
        assert result["existing"] == 0

        items = get_all_tracked_items(engine)
        assert len(items) == len(SEED_ITEMS)

    def test_all_marked_as_seeded(self, engine):
        seed_all(engine)

        seeded = get_seeded_items(engine)
        assert len(seeded) == len(SEED_ITEMS)
        assert all(s["is_seeded"] is True for s in seeded)

    def test_idempotent(self, engine):
        first = seed_all(engine)
        second = seed_all(engine)

        assert first["created"] == len(SEED_ITEMS)
        assert second["created"] == 0
        assert second["existing"] == len(SEED_ITEMS)

        # Still only one row per seed item
        assert len(get_all_tracked_items(engine)) == len(SEED_ITEMS)

    def test_display_names_set(self, engine):
        seed_all(engine)

        items = get_all_tracked_items(engine)
        display_names = {i["display_name"] for i in items}
        expected = {entry["display_name"] for entry in SEED_ITEMS}
        assert display_names == expected

    def test_all_start_as_collecting(self, engine):
        seed_all(engine)

        items = get_all_tracked_items(engine)
        assert all(i["status"] == "collecting" for i in items)

    def test_spans_multiple_categories(self):
        """Seed list should not be all one type of item."""
        queries = [e["query"].lower() for e in SEED_ITEMS]
        # At least one sneaker-ish, one electronics-ish, one collectible-ish
        has_sneaker = any(
            kw in q for q in queries
            for kw in ("jordan", "nike", "dunk", "new balance")
        )
        has_electronics = any(
            kw in q for q in queries
            for kw in ("playstation", "airpods", "switch", "iphone", "ps5")
        )
        has_collectible = any(
            kw in q for q in queries
            for kw in ("pokemon", "lego", "card", "vintage")
        )
        assert has_sneaker, "Seed list missing sneaker category"
        assert has_electronics, "Seed list missing electronics category"
        assert has_collectible, "Seed list missing collectible category"

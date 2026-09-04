"""Tests for the seed list setup."""

import pytest

from resale_price_agent.db import get_all_tracked_items, get_seeded_items
from resale_price_agent.seed_list import CATEGORIES, SEED_ITEMS, seed_all


class TestSeedAll:
    def test_creates_all_items(self, engine):
        result = seed_all(engine)

        assert result["created"] == len(SEED_ITEMS)
        assert result["existing"] == 0

        items = get_all_tracked_items(engine)
        assert len(items) == len(SEED_ITEMS)

    def test_item_count_in_range(self):
        assert 50 <= len(SEED_ITEMS) <= 100

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

    def test_no_duplicate_queries(self):
        """Every seed item must have a unique normalized query."""
        normalized = [e["query"].lower().strip() for e in SEED_ITEMS]
        assert len(normalized) == len(set(normalized))

    def test_every_item_has_category(self):
        for item in SEED_ITEMS:
            assert "category" in item, f"Missing category: {item['query']}"
            assert item["category"].strip(), f"Empty category: {item['query']}"

    def test_has_both_categories(self):
        """Seed list should have both sealed and graded categories."""
        assert "sealed" in CATEGORIES
        assert "graded" in CATEGORIES

    def test_all_items_are_pokemon(self):
        """Every seed item query should reference Pokemon."""
        for item in SEED_ITEMS:
            assert "pokemon" in item["query"].lower(), (
                f"Non-Pokemon item found: {item['query']}"
            )

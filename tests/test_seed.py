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

    def test_category_diversity(self):
        """Seed list should span at least 8 distinct categories."""
        assert len(CATEGORIES) >= 8

    def test_spans_expected_categories(self):
        """Verify key category types are represented."""
        queries = [e["query"].lower() for e in SEED_ITEMS]
        checks = {
            "sneakers": ("jordan", "nike", "dunk", "new balance", "yeezy", "adidas"),
            "gaming": ("playstation", "switch", "xbox", "steam deck"),
            "phones": ("iphone", "galaxy", "pixel", "ipad"),
            "audio": ("airpods", "sony wh", "bose", "sennheiser"),
            "trading_cards": ("pokemon", "topps", "panini", "magic the gathering", "yu-gi-oh"),
            "lego": ("lego",),
            "watches": ("casio", "seiko", "omega", "garmin", "apple watch"),
            "cameras": ("contax", "canon ae", "fujifilm", "gopro", "polaroid"),
            "streetwear": ("supreme", "fear of god", "stussy", "north face"),
            "home": ("dyson", "stanley", "vitamix", "le creuset", "yeti"),
        }
        for label, keywords in checks.items():
            found = any(kw in q for q in queries for kw in keywords)
            assert found, f"Seed list missing {label} category"

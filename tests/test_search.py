"""Tests for the public search flow."""

from datetime import datetime, timezone

import pytest

from resale_price_agent.db import (
    get_all_tracked_items,
    get_or_create_tracked_item,
    insert_decision,
    insert_snapshots,
)
from resale_price_agent.search import search


# ---------------------------------------------------------------------------
# Brand-new search
# ---------------------------------------------------------------------------

class TestNewSearch:
    def test_creates_tracked_item(self, engine):
        result = search(engine, "Jordan 4 Retro Military Black")

        assert result["created"] is True
        assert result["tracked_item"]["search_query"] == "Jordan 4 Retro Military Black"
        assert result["tracked_item"]["normalized_query"] == "jordan 4 retro military black"

    def test_new_item_is_collecting(self, engine):
        result = search(engine, "Jordan 4 Retro")

        assert result["status"] == "collecting"

    def test_new_item_has_empty_data(self, engine):
        result = search(engine, "Jordan 4 Retro")

        assert result["snapshots"] == []
        assert result["decisions"] == []
        assert result["snapshot_count"] == 0


# ---------------------------------------------------------------------------
# Existing search with data
# ---------------------------------------------------------------------------

class TestExistingSearch:
    def test_returns_existing_item(self, engine):
        # First search creates it
        search(engine, "Jordan 4 Retro")
        # Second search finds it
        result = search(engine, "Jordan 4 Retro")

        assert result["created"] is False

    def test_returns_snapshots_and_decisions(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        insert_snapshots(engine, item["id"], [
            {"ebay_item_id": "v1|111|0", "title": "Jordan 4", "price": 200.0},
            {"ebay_item_id": "v1|222|0", "title": "Jordan 4 Used", "price": 180.0},
        ])
        insert_decision(
            engine, item["id"], "llm_reasoning",
            action="wait", confidence=0.6, reasoning="Prices stable",
        )

        result = search(engine, "Jordan 4 Retro")

        assert result["created"] is False
        assert result["snapshot_count"] == 2
        assert len(result["snapshots"]) == 2
        assert len(result["decisions"]) == 1
        assert result["decisions"][0]["action"] == "wait"

    def test_no_duplicate_row(self, engine):
        search(engine, "Jordan 4 Retro")
        search(engine, "Jordan 4 Retro")
        search(engine, "Jordan 4 Retro")

        assert len(get_all_tracked_items(engine)) == 1


# ---------------------------------------------------------------------------
# Dedupe across variations
# ---------------------------------------------------------------------------

class TestDedupeVariations:
    def test_case_insensitive(self, engine):
        r1 = search(engine, "Jordan 4 Retro")
        r2 = search(engine, "jordan 4 retro")

        assert r1["tracked_item"]["id"] == r2["tracked_item"]["id"]
        assert r2["created"] is False

    def test_whitespace_insensitive(self, engine):
        r1 = search(engine, "Jordan 4 Retro")
        r2 = search(engine, "  Jordan   4   Retro  ")

        assert r1["tracked_item"]["id"] == r2["tracked_item"]["id"]
        assert r2["created"] is False

    def test_combined_case_and_whitespace(self, engine):
        r1 = search(engine, "Jordan 4 Retro")
        r2 = search(engine, "  JORDAN    4    RETRO  ")

        assert r1["tracked_item"]["id"] == r2["tracked_item"]["id"]
        assert r2["created"] is False
        assert len(get_all_tracked_items(engine)) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_query_raises(self, engine):
        with pytest.raises(ValueError, match="empty"):
            search(engine, "   ")

    def test_different_queries_are_separate(self, engine):
        r1 = search(engine, "Jordan 4 Retro")
        r2 = search(engine, "Nike Dunk Low")

        assert r1["tracked_item"]["id"] != r2["tracked_item"]["id"]
        assert r1["created"] is True
        assert r2["created"] is True

"""Tests for condition normalization and per-listing labels."""

import pytest

from resale_price_agent.conditions import (
    get_condition_groups,
    label_listings,
    normalize_condition,
)


# ---------------------------------------------------------------------------
# normalize_condition
# ---------------------------------------------------------------------------

class TestNormalizeCondition:
    # --- New tier ---
    @pytest.mark.parametrize("raw", [
        "New", "New with box", "New without box",
        "New with tags", "New without tags",
    ])
    def test_new_tier(self, raw):
        assert normalize_condition(raw) == "New"

    def test_new_case_insensitive(self):
        assert normalize_condition("NEW WITH BOX") == "New"
        assert normalize_condition("new without tags") == "New"

    # --- Open Box tier ---
    @pytest.mark.parametrize("raw", [
        "New Other / Open Box", "New Other", "Open box",
    ])
    def test_open_box_tier(self, raw):
        assert normalize_condition(raw) == "Open Box"

    # --- New with Defects tier ---
    @pytest.mark.parametrize("raw", [
        "New with Imperfections", "New with defects",
    ])
    def test_new_with_defects_tier(self, raw):
        assert normalize_condition(raw) == "New with Defects"

    # --- Refurbished tier ---
    @pytest.mark.parametrize("raw", [
        "Certified - Refurbished",
        "Excellent - Refurbished",
        "Very Good - Refurbished",
        "Good - Refurbished",
        "Certified / Professionally Refurbished",
    ])
    def test_refurbished_tier(self, raw):
        assert normalize_condition(raw) == "Refurbished"

    # --- Pre-owned tiers ---
    def test_preowned_excellent(self):
        assert normalize_condition("Pre-owned - Excellent") == "Pre-owned - Excellent"

    @pytest.mark.parametrize("raw", [
        "Pre-owned - Good", "Pre-owned", "Used",
    ])
    def test_preowned_good(self, raw):
        assert normalize_condition(raw) == "Pre-owned - Good"

    def test_preowned_fair(self):
        assert normalize_condition("Pre-owned - Fair") == "Pre-owned - Fair"

    # --- For Parts tier ---
    @pytest.mark.parametrize("raw", [
        "For Parts or Not Working", "For parts or not working",
    ])
    def test_for_parts_tier(self, raw):
        assert normalize_condition(raw) == "For Parts"

    # --- Other / fallback ---
    def test_none_maps_to_other(self):
        assert normalize_condition(None) == "Other"

    def test_empty_string_maps_to_other(self):
        assert normalize_condition("") == "Other"

    def test_unknown_string_maps_to_other(self):
        assert normalize_condition("Totally Unknown Condition") == "Other"


# ---------------------------------------------------------------------------
# get_condition_groups
# ---------------------------------------------------------------------------

class TestGetConditionGroups:
    def test_returns_sorted_tiers(self):
        snapshots = [
            {"condition": "New with box"},
            {"condition": "Pre-owned - Excellent"},
            {"condition": "New"},
            {"condition": "Used"},
        ]
        groups = get_condition_groups(snapshots)
        assert groups == ["New", "Pre-owned - Excellent", "Pre-owned - Good"]

    def test_empty_snapshots(self):
        assert get_condition_groups([]) == []

    def test_includes_other_for_missing_condition(self):
        snapshots = [
            {"condition": None},
            {"condition": "New"},
        ]
        groups = get_condition_groups(snapshots)
        assert "Other" in groups
        assert "New" in groups


# ---------------------------------------------------------------------------
# label_listings
# ---------------------------------------------------------------------------

class TestLabelListings:
    def _make_signals(self, median, sufficient=True):
        """Minimal mock for signals_by_condition values."""
        class FakeSignals:
            def __init__(self, m, s):
                self.latest_batch_median = m
                self.sufficient_data = s
        return FakeSignals(median, sufficient)

    def test_good_buy_below_threshold(self):
        signals_by_condition = {
            "New": self._make_signals(200.0),
        }
        snapshots = [
            {"id": 1, "ebay_item_id": "e1", "price": 175.0, "condition": "New"},
        ]
        labels = label_listings(snapshots, signals_by_condition)

        assert len(labels) == 1
        assert labels[0]["label"] == "Good Buy"
        assert labels[0]["vs_median_pct"] < -10
        assert labels[0]["condition_group"] == "New"

    def test_overpriced_above_threshold(self):
        signals_by_condition = {
            "New": self._make_signals(200.0),
        }
        snapshots = [
            {"id": 2, "ebay_item_id": "e2", "price": 225.0, "condition": "New"},
        ]
        labels = label_listings(snapshots, signals_by_condition)

        assert labels[0]["label"] == "Overpriced"
        assert labels[0]["vs_median_pct"] > 10

    def test_fair_price_within_range(self):
        signals_by_condition = {
            "New": self._make_signals(200.0),
        }
        snapshots = [
            {"id": 3, "ebay_item_id": "e3", "price": 205.0, "condition": "New"},
        ]
        labels = label_listings(snapshots, signals_by_condition)

        assert labels[0]["label"] == "Fair Price"

    def test_insufficient_data_no_label(self):
        signals_by_condition = {
            "New": self._make_signals(200.0, sufficient=False),
        }
        snapshots = [
            {"id": 4, "ebay_item_id": "e4", "price": 100.0, "condition": "New"},
        ]
        labels = label_listings(snapshots, signals_by_condition)

        assert len(labels) == 0

    def test_missing_condition_group_no_label(self):
        signals_by_condition = {}
        snapshots = [
            {"id": 5, "ebay_item_id": "e5", "price": 100.0, "condition": "New"},
        ]
        labels = label_listings(snapshots, signals_by_condition)

        assert len(labels) == 0

    def test_exact_threshold_boundaries(self):
        signals_by_condition = {
            "New": self._make_signals(100.0),
        }
        # Exactly -10% → Fair Price (not Good Buy)
        snapshots_low = [
            {"id": 6, "ebay_item_id": "e6", "price": 90.0, "condition": "New"},
        ]
        labels_low = label_listings(snapshots_low, signals_by_condition)
        assert labels_low[0]["label"] == "Fair Price"

        # Exactly +10% → Fair Price (not Overpriced)
        snapshots_high = [
            {"id": 7, "ebay_item_id": "e7", "price": 110.0, "condition": "New"},
        ]
        labels_high = label_listings(snapshots_high, signals_by_condition)
        assert labels_high[0]["label"] == "Fair Price"

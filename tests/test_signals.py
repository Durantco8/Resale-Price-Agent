"""Tests for signal computation — in-memory DB, no network."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import get_or_create_tracked_item, insert_snapshots, metadata
from resale_price_agent.signals import (
    TrendSignals,
    _compute_signals_from_snapshots,
    compute_signals,
    compute_signals_by_condition,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


def _snap(ebay_id, price, hours_ago=0, condition=""):
    return {
        "ebay_item_id": ebay_id,
        "title": "Test",
        "price": price,
        "condition": condition,
        "snapshot_time": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }


def _seed(engine, item_id, price_hour_pairs):
    """Insert one synthetic poll batch for each (price, hours_ago) pair."""
    for i, (price, hours_ago) in enumerate(price_hour_pairs):
        insert_snapshots(
            engine,
            item_id,
            [_snap(f"s-{hours_ago}-{i}", price, hours_ago=hours_ago)],
            poll_batch_id=f"batch-{hours_ago}",
        )


def _insert_batch(engine, item_id, prices, hours_ago, batch_id, condition=""):
    insert_snapshots(
        engine,
        item_id,
        [
            _snap(f"{batch_id}-{i}", price, hours_ago=hours_ago, condition=condition)
            for i, price in enumerate(prices)
        ],
        poll_batch_id=batch_id,
    )


# ---------------------------------------------------------------------------
# Cold start / insufficient data
# ---------------------------------------------------------------------------

class TestColdStart:
    def test_zero_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is False
        assert signals.avg_price is None
        assert signals.price_trend is None
        assert signals.listing_trend is None
        assert signals.snapshot_count == 0

    def test_below_min_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [(200.0, h) for h in range(4)])

        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is False
        assert signals.snapshot_count == 4

    def test_exactly_at_min_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [(200.0, h) for h in range(5)])

        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is True
        assert signals.snapshot_count == 5

    def test_custom_min_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [(200.0, h) for h in range(3)])

        signals = compute_signals(engine, item_id, min_snapshots=3)
        assert signals.sufficient_data is True

    def test_to_dict(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        signals = compute_signals(engine, item_id)
        d = signals.to_dict()

        assert isinstance(d, dict)
        assert d["sufficient_data"] is False
        assert "avg_price" in d


# ---------------------------------------------------------------------------
# Price stats
# ---------------------------------------------------------------------------

class TestPriceStats:
    def test_avg_min_max(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [
            (200.0, 10), (220.0, 8), (180.0, 6), (210.0, 4), (190.0, 2),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.avg_price == 200.0
        assert signals.min_price == 180.0
        assert signals.max_price == 220.0

    def test_identical_prices(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [(150.0, h) for h in range(6)])

        signals = compute_signals(engine, item_id)

        assert signals.avg_price == 150.0
        assert signals.min_price == 150.0
        assert signals.max_price == 150.0

    def test_window_excludes_old_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # 5 recent snapshots at $200
        _seed(engine, item_id, [(200.0, h) for h in range(5)])
        # 5 old snapshots at $100, outside default 14-day window
        old_snaps = [
            _snap(f"old-{i}", 100.0, hours_ago=400 + i) for i in range(5)
        ]
        insert_snapshots(engine, item_id, old_snaps)

        signals = compute_signals(engine, item_id, window_days=14)

        assert signals.avg_price == 200.0
        assert signals.snapshot_count == 5


# ---------------------------------------------------------------------------
# Price trend
# ---------------------------------------------------------------------------

class TestPriceTrend:
    def test_rising_prices(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # Older half: low prices, newer half: higher prices
        _seed(engine, item_id, [
            (100.0, 48), (100.0, 44), (100.0, 40),  # older
            (120.0, 12), (120.0, 8), (120.0, 4),     # newer
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "rising"
        assert signals.price_trend_pct > 0

    def test_falling_prices(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 44), (200.0, 40),  # older
            (170.0, 12), (170.0, 8), (170.0, 4),     # newer
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "falling"
        assert signals.price_trend_pct < 0

    def test_flat_prices(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 44), (200.0, 40),
            (201.0, 12), (199.0, 8), (200.0, 4),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "flat"

    def test_small_change_is_flat(self, engine):
        """Changes under 2% should be classified as flat."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 44), (200.0, 40),
            (203.0, 12), (203.0, 8), (203.0, 4),  # 1.5% rise
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "flat"
        assert signals.price_trend_pct > 0  # still reports the actual pct


# ---------------------------------------------------------------------------
# Listing count trend
# ---------------------------------------------------------------------------

class TestListingTrend:
    def test_rising_supply(self, engine):
        """More unique listings in newer poll batches = rising supply."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [200.0], 72, "old-1")
        _insert_batch(engine, item_id, [200.0], 48, "old-2")
        _insert_batch(engine, item_id, [200.0] * 3, 6, "new-1")
        _insert_batch(engine, item_id, [200.0] * 3, 3, "new-2")

        signals = compute_signals(engine, item_id)

        assert signals.listing_trend == "rising"

    def test_falling_supply(self, engine):
        """Fewer unique listings in newer poll batches = falling supply."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [200.0] * 3, 72, "old-1")
        _insert_batch(engine, item_id, [200.0] * 3, 48, "old-2")
        _insert_batch(engine, item_id, [200.0], 6, "new-1")
        _insert_batch(engine, item_id, [200.0], 3, "new-2")

        signals = compute_signals(engine, item_id)

        assert signals.listing_trend == "falling"

    def test_stable_supply(self, engine):
        """Same unique-listing count per batch = flat."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        for index, hours_ago in enumerate((144, 120, 96, 72, 48, 24)):
            _insert_batch(
                engine, item_id, [200.0], hours_ago, f"batch-{index}",
            )

        signals = compute_signals(engine, item_id)

        assert signals.listing_trend == "flat"


# ---------------------------------------------------------------------------
# Poll-batch maturity and robust metrics
# ---------------------------------------------------------------------------

class TestPollBatchMetrics:
    def test_one_large_batch_does_not_create_a_trend(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(
            engine, item_id,
            [100.0, 100.0, 100.0, 140.0, 140.0, 140.0],
            2, "only-poll",
        )

        signals = compute_signals(engine, item_id)

        assert signals.snapshot_count == 6
        assert signals.poll_batch_count == 1
        assert signals.sufficient_data is False
        assert signals.price_trend is None
        assert signals.listing_trend is None

    def test_separate_batches_drive_price_trend(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [98.0, 100.0, 102.0], 48, "older")
        _insert_batch(engine, item_id, [118.0, 120.0, 122.0], 2, "newer")

        signals = compute_signals(engine, item_id)

        assert signals.poll_batch_count == 2
        assert signals.sufficient_data is True
        assert signals.price_trend == "rising"
        assert signals.price_trend_pct == 20.0
        assert signals.latest_batch_median == 120.0
        assert signals.historical_median == 100.0
        assert signals.median_batch_price == 110.0

    def test_robust_dispersion_unique_listings_and_history_span(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [100.0, 110.0, 120.0], 72, "older")
        insert_snapshots(
            engine,
            item_id,
            [
                _snap("repeat", 130.0, 1),
                _snap("repeat", 140.0, 1),
                _snap("unique", 150.0, 1),
            ],
            poll_batch_id="newer",
        )

        signals = compute_signals(engine, item_id)

        assert signals.unique_listing_count == 5
        assert signals.latest_batch_listing_count == 2
        assert signals.price_p25 == 112.5
        assert signals.price_p75 == 137.5
        assert signals.price_iqr == 25.0
        assert 2.9 < signals.history_span_days < 3.0
        assert 0.9 < signals.freshness_hours < 1.1


# ---------------------------------------------------------------------------
# to_dict for LLM handoff
# ---------------------------------------------------------------------------

class TestToDict:
    def test_sufficient_data_dict(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed(engine, item_id, [(200.0, h) for h in range(6)])

        d = compute_signals(engine, item_id).to_dict()

        assert d["sufficient_data"] is True
        assert isinstance(d["avg_price"], float)
        assert isinstance(d["price_trend"], str)
        assert isinstance(d["window_days"], int)

    def test_insufficient_data_dict(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]

        d = compute_signals(engine, item_id).to_dict()

        assert d["sufficient_data"] is False
        assert d["avg_price"] is None
        assert d["price_trend"] is None


# ---------------------------------------------------------------------------
# Condition-segmented signals
# ---------------------------------------------------------------------------

class TestConditionSignals:
    def test_compute_from_snapshots_matches_compute_signals(self, engine):
        """_compute_signals_from_snapshots with fetched data matches compute_signals."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [100.0, 110.0, 120.0], 48, "b1")
        _insert_batch(engine, item_id, [130.0, 140.0, 150.0], 2, "b2")

        full = compute_signals(engine, item_id)

        from resale_price_agent.db import get_snapshots_for_item
        snaps = get_snapshots_for_item(engine, item_id)
        manual = _compute_signals_from_snapshots(snaps)

        assert manual.avg_price == full.avg_price
        assert manual.price_trend == full.price_trend
        assert manual.snapshot_count == full.snapshot_count
        assert manual.poll_batch_count == full.poll_batch_count

    def test_by_condition_returns_all_key(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [200.0] * 3, 48, "b1", condition="New")
        _insert_batch(engine, item_id, [200.0] * 3, 2, "b2", condition="New")

        result = compute_signals_by_condition(engine, item_id)

        assert "All" in result
        assert "New" in result
        assert result["All"].sufficient_data is True

    def test_by_condition_separates_tiers(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # New items: $300
        _insert_batch(engine, item_id, [300.0] * 3, 48, "b1-new", condition="New with box")
        _insert_batch(engine, item_id, [300.0] * 3, 2, "b2-new", condition="New with box")
        # Pre-owned: $150
        _insert_batch(engine, item_id, [150.0] * 3, 48, "b1-used", condition="Used")
        _insert_batch(engine, item_id, [150.0] * 3, 2, "b2-used", condition="Used")

        result = compute_signals_by_condition(engine, item_id)

        assert "New" in result
        assert "Pre-owned - Good" in result
        assert result["New"].avg_price == 300.0
        assert result["Pre-owned - Good"].avg_price == 150.0
        # All should average both
        assert result["All"].avg_price == 225.0

    def test_sparse_tier_insufficient_data(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # Only 2 snapshots for "New" — below MIN_SNAPSHOTS
        _insert_batch(engine, item_id, [300.0, 310.0], 2, "b1", condition="New")

        result = compute_signals_by_condition(engine, item_id)

        assert result["New"].sufficient_data is False

    def test_all_matches_aggregate_regression(self, engine):
        """'All' key must match existing compute_signals behavior."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _insert_batch(engine, item_id, [100.0, 200.0, 300.0], 48, "b1", condition="New")
        _insert_batch(engine, item_id, [110.0, 210.0, 310.0], 2, "b2", condition="Used")

        aggregate = compute_signals(engine, item_id)
        by_cond = compute_signals_by_condition(engine, item_id)

        assert by_cond["All"].avg_price == aggregate.avg_price
        assert by_cond["All"].snapshot_count == aggregate.snapshot_count
        assert by_cond["All"].price_trend == aggregate.price_trend

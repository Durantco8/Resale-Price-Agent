"""Tests for signal computation — in-memory DB, no network."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import add_tracked_item, insert_snapshots, metadata
from resale_price_agent.signals import TrendSignals, compute_signals


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


def _snap(ebay_id, price, hours_ago=0):
    return {
        "ebay_item_id": ebay_id,
        "title": "Test",
        "price": price,
        "snapshot_time": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }


def _seed(engine, item_id, price_hour_pairs):
    """Insert snapshots from a list of (price, hours_ago) tuples."""
    snaps = [
        _snap(f"s-{i}", price, hours_ago=h)
        for i, (price, h) in enumerate(price_hour_pairs)
    ]
    insert_snapshots(engine, item_id, snaps)


# ---------------------------------------------------------------------------
# Cold start / insufficient data
# ---------------------------------------------------------------------------

class TestColdStart:
    def test_zero_snapshots(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is False
        assert signals.avg_price is None
        assert signals.price_trend is None
        assert signals.listing_trend is None
        assert signals.snapshot_count == 0

    def test_below_min_snapshots(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [(200.0, h) for h in range(4)])

        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is False
        assert signals.snapshot_count == 4

    def test_exactly_at_min_snapshots(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [(200.0, h) for h in range(5)])

        signals = compute_signals(engine, item_id)

        assert signals.sufficient_data is True
        assert signals.snapshot_count == 5

    def test_custom_min_snapshots(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [(200.0, h) for h in range(3)])

        signals = compute_signals(engine, item_id, min_snapshots=3)
        assert signals.sufficient_data is True

    def test_to_dict(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
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
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [
            (200.0, 10), (220.0, 8), (180.0, 6), (210.0, 4), (190.0, 2),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.avg_price == 200.0
        assert signals.min_price == 180.0
        assert signals.max_price == 220.0

    def test_identical_prices(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [(150.0, h) for h in range(6)])

        signals = compute_signals(engine, item_id)

        assert signals.avg_price == 150.0
        assert signals.min_price == 150.0
        assert signals.max_price == 150.0

    def test_window_excludes_old_snapshots(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
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
        item_id = add_tracked_item(engine, "Jordan 4")
        # Older half: low prices, newer half: higher prices
        _seed(engine, item_id, [
            (100.0, 48), (100.0, 44), (100.0, 40),  # older
            (120.0, 12), (120.0, 8), (120.0, 4),     # newer
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "rising"
        assert signals.price_trend_pct > 0

    def test_falling_prices(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 44), (200.0, 40),  # older
            (170.0, 12), (170.0, 8), (170.0, 4),     # newer
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "falling"
        assert signals.price_trend_pct < 0

    def test_flat_prices(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 44), (200.0, 40),
            (201.0, 12), (199.0, 8), (200.0, 4),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.price_trend == "flat"

    def test_small_change_is_flat(self, engine):
        """Changes under 2% should be classified as flat."""
        item_id = add_tracked_item(engine, "Jordan 4")
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
        """More listings per day in newer half = rising supply."""
        item_id = add_tracked_item(engine, "Jordan 4")
        # Older: 1 listing per day across 3 days
        _seed(engine, item_id, [
            (200.0, 72), (200.0, 48), (200.0, 24),
        ])
        # Newer: 3 listings on one day (= higher daily count)
        _seed(engine, item_id, [
            (200.0, 3), (200.0, 2), (200.0, 1),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.listing_trend == "rising"

    def test_falling_supply(self, engine):
        """Fewer listings per day in newer half = falling supply."""
        item_id = add_tracked_item(engine, "Jordan 4")
        # Older: 3 listings on one day
        _seed(engine, item_id, [
            (200.0, 73), (200.0, 72), (200.0, 71),
        ])
        # Newer: 1 listing per day across 3 days
        _seed(engine, item_id, [
            (200.0, 48), (200.0, 24), (200.0, 1),
        ])

        signals = compute_signals(engine, item_id)

        assert signals.listing_trend == "falling"

    def test_stable_supply(self, engine):
        """Same daily counts = flat."""
        item_id = add_tracked_item(engine, "Jordan 4")
        # 1 listing per day, spread across 6 distinct days
        _seed(engine, item_id, [
            (200.0, 144), (200.0, 120), (200.0, 96),
            (200.0, 72), (200.0, 48), (200.0, 24),
        ])

        signals = compute_signals(engine, item_id)

        # 1 listing per day in both halves — trend should be flat
        assert signals.listing_trend == "flat"


# ---------------------------------------------------------------------------
# to_dict for LLM handoff
# ---------------------------------------------------------------------------

class TestToDict:
    def test_sufficient_data_dict(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed(engine, item_id, [(200.0, h) for h in range(6)])

        d = compute_signals(engine, item_id).to_dict()

        assert d["sufficient_data"] is True
        assert isinstance(d["avg_price"], float)
        assert isinstance(d["price_trend"], str)
        assert isinstance(d["window_days"], int)

    def test_insufficient_data_dict(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")

        d = compute_signals(engine, item_id).to_dict()

        assert d["sufficient_data"] is False
        assert d["avg_price"] is None
        assert d["price_trend"] is None

"""Tests for deterministic price-drop detection."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import (
    get_or_create_tracked_item,
    get_decisions_for_item,
    insert_snapshots,
    metadata,
)
from resale_price_agent.price_drop import check_price_drops


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


def _snap(ebay_id, price, hours_ago=0, title="Test Item"):
    """Build a snapshot dict with a timestamp relative to now."""
    return {
        "ebay_item_id": ebay_id,
        "title": title,
        "price": price,
        "currency": "USD",
        "snapshot_time": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }


def _seed_history(engine, item_id, prices, start_hours_ago=48):
    """Insert historical snapshots at evenly-spaced times."""
    snaps = []
    for i, price in enumerate(prices):
        snaps.append(
            _snap(f"hist-{i}", price, hours_ago=start_hours_ago - i)
        )
    insert_snapshots(engine, item_id, snaps)


def _ensure_baseline(engine, item_id, price=200.0):
    """Insert one prior snapshot so the cold-start guard passes.

    The cold-start guard skips all alerts on the very first poll
    (zero prior snapshots) to establish a baseline.  Call this in any
    test that needs price-drop detection to actually run.
    """
    insert_snapshots(engine, item_id, [_snap("baseline-0", price, hours_ago=72)])


# ---------------------------------------------------------------------------
# Cold-start guard
# ---------------------------------------------------------------------------

class TestColdStartGuard:
    def test_first_poll_target_price_still_fires(self, engine):
        """First poll fires target-price alerts — a real deal is actionable."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        new = [_snap("new-1", 50.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=200.0)
        assert len(alerts) == 1
        decisions = get_decisions_for_item(engine, item_id)
        assert "target price" in decisions[0]["reasoning"]

    def test_first_poll_no_avg_alert(self, engine):
        """First poll never fires rolling-average alerts (no history yet)."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        new = [_snap("new-1", 50.0)]

        # No target price → only way to alert is rolling avg, which is skipped
        alerts = check_price_drops(engine, item_id, new, target_price=None)
        assert len(alerts) == 0

    def test_first_poll_target_respects_daily_cap(self, engine):
        """First-poll target-price alerts still obey the daily cap."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        new = [_snap(f"new-{i}", 10.0) for i in range(50)]

        alerts = check_price_drops(
            engine, item_id, new, target_price=200.0, daily_cap=3,
        )
        assert len(alerts) == 3

    def test_second_poll_fires_normally(self, engine):
        """After baseline is established, alerts fire on the next poll."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]

        # First poll — silent baseline
        first_batch = [_snap("baseline", 220.0)]
        insert_snapshots(engine, item_id, first_batch)
        alerts_first = check_price_drops(
            engine, item_id, first_batch, target_price=200.0,
        )
        assert len(alerts_first) == 0  # above target, no alert anyway

        # Second poll — real drop, should fire
        second_batch = [_snap("new-1", 180.0)]
        alerts_second = check_price_drops(
            engine, item_id, second_batch, target_price=200.0,
        )
        assert len(alerts_second) == 1


# ---------------------------------------------------------------------------
# Target price checks
# ---------------------------------------------------------------------------

class TestTargetPrice:
    def test_below_target_fires(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        new = [_snap("new-1", 189.99)]

        alerts = check_price_drops(engine, item_id, new, target_price=200.0)

        assert len(alerts) == 1
        decisions = get_decisions_for_item(engine, item_id)
        assert decisions[0]["event_type"] == "price_drop_alert"
        assert "below target price" in decisions[0]["reasoning"]

    def test_at_target_fires(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        new = [_snap("new-1", 200.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=200.0)
        assert len(alerts) == 1

    def test_above_target_no_alert(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        new = [_snap("new-1", 200.01)]

        alerts = check_price_drops(engine, item_id, new, target_price=200.0)
        assert len(alerts) == 0

    def test_no_target_set(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        new = [_snap("new-1", 100.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=None)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Rolling average checks
# ---------------------------------------------------------------------------

class TestRollingAverage:
    def test_below_threshold_fires(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # History: 10 snapshots averaging $220
        _seed_history(engine, item_id, [220.0] * 10)
        # New listing at $190 = ~13.6% below average (> 12% default)
        new = [_snap("new-1", 190.0)]

        alerts = check_price_drops(engine, item_id, new)

        assert len(alerts) == 1
        decisions = get_decisions_for_item(engine, item_id)
        assert "below" in decisions[0]["reasoning"]
        assert "average" in decisions[0]["reasoning"]
        signals = json.loads(decisions[0]["computed_signals"])
        assert signals["rolling_avg"] == 220.0
        assert signals["pct_below_avg"] > 12

    def test_just_above_threshold_no_alert(self, engine):
        """11.9% below average should NOT fire at the 12% threshold."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [200.0] * 10)
        # 200 * 0.88 = 176.  A price of 176.50 is ~11.75% below — no alert.
        new = [_snap("new-1", 176.50)]

        alerts = check_price_drops(engine, item_id, new, drop_threshold=0.12)
        assert len(alerts) == 0

    def test_just_below_threshold_fires(self, engine):
        """12.5% below average SHOULD fire at the 12% threshold."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [200.0] * 10)
        # 200 * 0.875 = 175.  Price of 175 is exactly 12.5% below.
        new = [_snap("new-1", 175.0)]

        alerts = check_price_drops(engine, item_id, new, drop_threshold=0.12)
        assert len(alerts) == 1

    def test_exactly_at_threshold_fires(self, engine):
        """Exactly 12% below should fire (>= threshold)."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [200.0] * 10)
        # 200 * 0.88 = 176.0 exactly
        new = [_snap("new-1", 176.0)]

        alerts = check_price_drops(engine, item_id, new, drop_threshold=0.12)
        assert len(alerts) == 1

    def test_custom_threshold(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [200.0] * 10)
        # 5% threshold: $190 is exactly 5% below
        new = [_snap("new-1", 190.0)]

        alerts = check_price_drops(engine, item_id, new, drop_threshold=0.05)
        assert len(alerts) == 1

    def test_price_above_average_no_alert(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [200.0] * 10)
        new = [_snap("new-1", 210.0)]

        alerts = check_price_drops(engine, item_id, new)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Cold start (insufficient history for rolling avg, but past first poll)
# ---------------------------------------------------------------------------

class TestColdStart:
    def test_too_few_snapshots_skips_avg_check(self, engine):
        """With < min_history snapshots, rolling avg check is skipped."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        # Only 3 snapshots (default min is 5) — but enough to pass cold-start guard
        _seed_history(engine, item_id, [220.0, 220.0, 220.0])
        # This price would be way below average, but avg check should be skipped
        new = [_snap("new-1", 100.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=None)
        assert len(alerts) == 0

    def test_zero_history_is_cold_start(self, engine):
        """Zero prior snapshots = first poll = no alerts."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        new = [_snap("new-1", 100.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=None)
        assert len(alerts) == 0

    def test_cold_start_target_still_fires(self, engine):
        """First poll fires target-price alerts even with no history."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        new = [_snap("new-1", 150.0)]

        alerts = check_price_drops(engine, item_id, new, target_price=180.0)
        assert len(alerts) == 1


# ---------------------------------------------------------------------------
# Multiple listings / combined triggers
# ---------------------------------------------------------------------------

class TestMultipleListings:
    def test_multiple_new_listings(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [220.0] * 10)
        new = [
            _snap("new-1", 190.0),  # 13.6% below — fires
            _snap("new-2", 215.0),  # 2.3% below — no alert
            _snap("new-3", 185.0),  # 15.9% below — fires
        ]

        alerts = check_price_drops(engine, item_id, new)
        assert len(alerts) == 2

    def test_both_target_and_avg_fire(self, engine):
        """A listing can trigger both checks at once."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [220.0] * 10)
        new = [_snap("new-1", 180.0)]

        alerts = check_price_drops(
            engine, item_id, new, target_price=190.0
        )
        assert len(alerts) == 1
        decisions = get_decisions_for_item(engine, item_id)
        reasoning = decisions[0]["reasoning"]
        assert "target price" in reasoning
        assert "average" in reasoning

    def test_empty_new_snapshots(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        alerts = check_price_drops(engine, item_id, [])
        assert alerts == []


# ---------------------------------------------------------------------------
# Signals stored correctly
# ---------------------------------------------------------------------------

class TestSignals:
    def test_signals_contain_expected_keys(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _seed_history(engine, item_id, [220.0] * 10)
        new = [_snap("new-1", 190.0, title="Jordan 4 Military Black")]

        check_price_drops(engine, item_id, new)

        decisions = get_decisions_for_item(engine, item_id)
        signals = json.loads(decisions[0]["computed_signals"])
        assert "listing_price" in signals
        assert "rolling_avg" in signals
        assert "pct_below_avg" in signals
        assert "ebay_item_id" in signals
        assert signals["ebay_item_id"] == "new-1"
        assert signals["title"] == "Jordan 4 Military Black"


# ---------------------------------------------------------------------------
# Throttling — dedup and daily cap
# ---------------------------------------------------------------------------

class TestThrottlingDedup:
    def test_same_listing_twice_only_one_alert(self, engine):
        """Same eBay listing ID across two poll cycles → only the first fires."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        snap = [_snap("listing-A", 180.0)]

        first = check_price_drops(engine, item_id, snap, target_price=200.0)
        second = check_price_drops(engine, item_id, snap, target_price=200.0)

        assert len(first) == 1
        assert len(second) == 0

    def test_different_listings_both_alert(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)

        a1 = check_price_drops(
            engine, item_id, [_snap("listing-A", 180.0)], target_price=200.0,
        )
        a2 = check_price_drops(
            engine, item_id, [_snap("listing-B", 175.0)], target_price=200.0,
        )

        assert len(a1) == 1
        assert len(a2) == 1

    def test_same_listing_in_one_batch_deduped(self, engine):
        """Two snapshots with the same eBay ID in one call → one alert."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        snaps = [
            _snap("listing-A", 180.0),
            _snap("listing-A", 179.0),
        ]

        alerts = check_price_drops(engine, item_id, snaps, target_price=200.0)
        assert len(alerts) == 1

    def test_dedup_window_expiry_allows_realert(self, engine):
        """After the dedup window passes, the same listing can re-alert."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        snap = [_snap("listing-A", 180.0)]

        first = check_price_drops(
            engine, item_id, snap, target_price=200.0, dedup_window_hours=1,
        )
        assert len(first) == 1

        # Move the existing alert's timestamp back 2 hours so it's outside
        # the 1-hour window.
        from resale_price_agent.db import decisions as dec_table
        with engine.begin() as conn:
            conn.execute(
                dec_table.update()
                .where(dec_table.c.id == first[0])
                .values(timestamp=datetime.now(timezone.utc) - timedelta(hours=2))
            )

        second = check_price_drops(
            engine, item_id, snap, target_price=200.0, dedup_window_hours=1,
        )
        assert len(second) == 1


class TestThrottlingDailyCap:
    def test_cap_stops_further_alerts(self, engine):
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)
        snaps = [_snap(f"listing-{i}", 180.0) for i in range(5)]

        alerts = check_price_drops(
            engine, item_id, snaps, target_price=200.0, daily_cap=3,
        )

        assert len(alerts) == 3

    def test_cap_counts_existing_alerts(self, engine):
        """Cap accounts for alerts already fired earlier today."""
        item_id = get_or_create_tracked_item(engine, "Jordan 4")[0]["id"]
        _ensure_baseline(engine, item_id)

        # Fire 2 alerts first
        first = check_price_drops(
            engine, item_id,
            [_snap("a", 180.0), _snap("b", 180.0)],
            target_price=200.0, daily_cap=3,
        )
        assert len(first) == 2

        # Only 1 more should be allowed
        second = check_price_drops(
            engine, item_id,
            [_snap("c", 180.0), _snap("d", 180.0)],
            target_price=200.0, daily_cap=3,
        )
        assert len(second) == 1

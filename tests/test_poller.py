"""Tests for the unified polling loop — all external calls faked."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from resale_price_agent.db import (
    get_all_tracked_items,
    get_decisions_for_item,
    get_or_create_tracked_item,
    get_snapshots_for_item,
    get_tracked_item,
    insert_snapshots,
    seed_tracked_item,
    set_tracked_item_status,
)
from resale_price_agent.ebay_client import ListingSnapshot
from resale_price_agent.poller import poll_all_items, snapshot_to_dict


# ---------------------------------------------------------------------------
# Test helpers — lightweight fakes (not from conftest, to avoid import issues)
# ---------------------------------------------------------------------------

def _listing(item_id="v1|123|0", price=200.0, **kw):
    defaults = dict(
        title="Test Listing", price_amount=price, price_currency="USD",
        condition="New", seller_feedback_score=100,
        item_url="https://www.ebay.com/itm/123", shipping_cost=5.99,
        item_location="New York, NY, US", buying_options=["FIXED_PRICE"],
        snapshot_time=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(kw)
    defaults["item_id"] = item_id
    return ListingSnapshot(**defaults)


class _MockEbay:
    def __init__(self, listings=None):
        self._listings = listings if listings is not None else [_listing()]
        self.search_calls = []

    def search_listings(self, query, limit=50, category_ids=None):
        self.search_calls.append(query)
        return list(self._listings)


class _PerQueryEbay:
    def __init__(self, responses):
        self._responses = responses

    def search_listings(self, query, limit=50, category_ids=None):
        resp = self._responses.get(query, [])
        if isinstance(resp, Exception):
            raise resp
        return resp


class _MockLLM:
    def __init__(self, action="wait", confidence=0.5, reasoning="Holding."):
        text = json.dumps({"action": action, "confidence": confidence, "reasoning": reasoning})
        self.models = self
        self._text = text

    def generate_content(self, **kwargs):
        class _R:
            pass
        r = _R()
        r.text = self._text
        return r


class _FailingLLM:
    def __init__(self):
        self.models = self

    def generate_content(self, **kwargs):
        raise ConnectionError("LLM API unavailable")


def _seed_history(engine, item_id, prices, start_hours_ago=48):
    snaps = []
    for i, price in enumerate(prices):
        snaps.append({
            "ebay_item_id": f"hist-{i}",
            "title": "Historical",
            "price": price,
            "snapshot_time": (
                datetime.now(timezone.utc)
                - timedelta(hours=start_hours_ago - i)
            ),
        })
    insert_snapshots(engine, item_id, snaps)


# ---------------------------------------------------------------------------
# snapshot_to_dict
# ---------------------------------------------------------------------------

class TestSnapshotToDict:
    def test_converts_all_fields(self):
        listing = _listing(
            item_id="v1|111|0", title="Jordan 4 Military Black",
            price=219.99, condition="New with box",
            seller_feedback_score=5000, shipping_cost=14.95,
            item_location="Portland, OR, US",
        )
        d = snapshot_to_dict(listing)

        assert d["ebay_item_id"] == "v1|111|0"
        assert d["title"] == "Jordan 4 Military Black"
        assert d["price"] == 219.99
        assert d["condition"] == "New with box"
        assert d["buying_format"] == "FIXED_PRICE"

    def test_multiple_buying_options(self):
        listing = _listing(buying_options=["FIXED_PRICE", "BEST_OFFER"])
        assert snapshot_to_dict(listing)["buying_format"] == "FIXED_PRICE, BEST_OFFER"

    def test_empty_buying_options(self):
        listing = _listing(buying_options=[])
        assert snapshot_to_dict(listing)["buying_format"] is None


# ---------------------------------------------------------------------------
# Basic polling
# ---------------------------------------------------------------------------

class TestPollBasics:
    def test_no_tracked_items(self, engine):
        result = poll_all_items(engine, _MockEbay(), _MockLLM())
        assert result["processed"] == 0
        assert result["failed"] == 0

    def test_single_item(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        ebay = _MockEbay([_listing(item_id="v1|111|0"), _listing(item_id="v1|222|0")])

        result = poll_all_items(engine, ebay, _MockLLM())

        assert result["processed"] == 1
        assert result["total_snapshots"] == 2
        assert len(get_snapshots_for_item(engine, item["id"])) == 2

    def test_multiple_items(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4")
        get_or_create_tracked_item(engine, "Nike Dunk")

        ebay = _MockEbay([_listing()])
        result = poll_all_items(engine, ebay, _MockLLM())

        assert result["processed"] == 2
        assert len(ebay.search_calls) == 2

    def test_seeded_and_user_items_both_polled(self, engine):
        seed_tracked_item(engine, "PS5 Console")
        get_or_create_tracked_item(engine, "Jordan 4")

        ebay = _MockEbay([_listing()])
        result = poll_all_items(engine, ebay, _MockLLM())

        assert result["processed"] == 2


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------

class TestFailureIsolation:
    def test_ebay_failure_doesnt_block_others(self, engine):
        get_or_create_tracked_item(engine, "Good item")
        get_or_create_tracked_item(engine, "Bad item")
        get_or_create_tracked_item(engine, "Also good")

        ebay = _PerQueryEbay({
            "Good item": [_listing(item_id="a")],
            "Bad item": ConnectionError("eBay timeout"),
            "Also good": [_listing(item_id="c")],
        })

        result = poll_all_items(engine, ebay, _MockLLM())

        assert result["processed"] == 2
        assert result["failed"] == 1

    def test_llm_failure_doesnt_block_others(self, engine):
        get_or_create_tracked_item(engine, "Item A")
        get_or_create_tracked_item(engine, "Item B")

        # Seed enough history so LLM actually runs
        items = get_all_tracked_items(engine)
        for item in items:
            _seed_history(engine, item["id"], [200.0] * 6)

        ebay = _MockEbay([_listing()])
        # LLM errors are caught inside get_llm_decision, not poll_all_items
        result = poll_all_items(engine, ebay, _FailingLLM())

        assert result["processed"] == 2
        assert result["failed"] == 0  # LLM errors handled internally


# ---------------------------------------------------------------------------
# Status transition: collecting → active
# ---------------------------------------------------------------------------

class TestStatusTransition:
    def test_stays_collecting_below_threshold(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0, 210.0, 205.0])

        # Poll adds 1 → 4 total, still below default threshold of 5
        ebay = _MockEbay([_listing()])
        poll_all_items(engine, ebay, _MockLLM())

        refreshed = get_tracked_item(engine, item["id"])
        assert refreshed["status"] == "collecting"

    def test_flips_to_active_at_threshold(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0, 210.0, 205.0, 195.0])

        # Poll adds 1 → 5 total, hits threshold
        ebay = _MockEbay([_listing()])
        poll_all_items(engine, ebay, _MockLLM())

        refreshed = get_tracked_item(engine, item["id"])
        assert refreshed["status"] == "active"

    def test_already_active_stays_active(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0] * 10)
        set_tracked_item_status(engine, item["id"], "active")

        ebay = _MockEbay([_listing()])
        poll_all_items(engine, ebay, _MockLLM())

        refreshed = get_tracked_item(engine, item["id"])
        assert refreshed["status"] == "active"

    def test_custom_threshold(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0, 210.0])

        # 2 existing + 1 from poll = 3, with threshold=3 should flip
        ebay = _MockEbay([_listing()])
        poll_all_items(engine, ebay, _MockLLM(), status_threshold=3)

        refreshed = get_tracked_item(engine, item["id"])
        assert refreshed["status"] == "active"


# ---------------------------------------------------------------------------
# Snapshot accumulation across poll cycles
# ---------------------------------------------------------------------------

class TestSnapshotAccumulation:
    def test_snapshots_accumulate(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        ebay = _MockEbay([_listing(item_id="v1|111|0")])
        llm = _MockLLM()

        poll_all_items(engine, ebay, llm)
        poll_all_items(engine, ebay, llm)
        poll_all_items(engine, ebay, llm)

        snaps = get_snapshots_for_item(engine, item["id"])
        assert len(snaps) == 3

    def test_count_accurate_after_multiple_cycles(self, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        listings = [_listing(item_id=f"v1|{i}|0", price=200.0 + i) for i in range(3)]
        ebay = _MockEbay(listings)
        llm = _MockLLM()

        poll_all_items(engine, ebay, llm)  # +3
        poll_all_items(engine, ebay, llm)  # +3

        snaps = get_snapshots_for_item(engine, item["id"])
        assert len(snaps) == 6


# ---------------------------------------------------------------------------
# Price-drop detection runs for all items
# ---------------------------------------------------------------------------

class TestPriceDropDetection:
    def test_price_drop_runs_for_all_items(self, engine):
        get_or_create_tracked_item(engine, "Item A", owner="me")
        get_or_create_tracked_item(engine, "Item B")  # public

        # Seed enough history so rolling avg exists
        items = get_all_tracked_items(engine)
        for item in items:
            _seed_history(engine, item["id"], [200.0] * 6)

        # Very cheap listing triggers price-drop detection
        ebay = _MockEbay([_listing(item_id="v1|cheap|0", price=100.0)])
        result = poll_all_items(engine, ebay, _MockLLM())

        # Both items processed, decisions stored for both
        assert result["processed"] == 2
        for item in items:
            decisions = get_decisions_for_item(engine, item["id"])
            assert any(d["event_type"] == "price_drop_alert" for d in decisions)


# ---------------------------------------------------------------------------
# Owner-gated personal notifications
# ---------------------------------------------------------------------------

class TestOwnerNotifications:
    def test_owner_item_triggers_personal_notify(self, engine):
        get_or_create_tracked_item(engine, "Jordan 4", owner="me")
        _seed_history(engine, 1, [200.0] * 6)

        ebay = _MockEbay([_listing(item_id="v1|cheap|0", price=100.0)])
        llm = _MockLLM(action="buy_now", confidence=0.9, reasoning="Great deal.")
        mock_notify_fn = MagicMock()

        result = poll_all_items(
            engine, ebay, llm,
            notify_send_fn=mock_notify_fn,
            notify_recipient="owner@example.com",
        )

        assert result["notifications"] > 0
        assert mock_notify_fn.call_count > 0
        # Every personal notification goes to the owner's email
        for call in mock_notify_fn.call_args_list:
            assert call[0][0] == "owner@example.com"

    def test_public_item_never_triggers_personal_notify(self, engine):
        """Inverse regression: public items must never call notifier.notify(),
        regardless of price drops, buy_now decisions, or any other condition."""
        get_or_create_tracked_item(engine, "Nintendo Switch OLED")  # owner=NULL
        _seed_history(engine, 1, [200.0] * 6)

        ebay = _MockEbay([_listing(item_id="v1|cheap|0", price=100.0)])
        llm = _MockLLM(action="buy_now", confidence=0.95, reasoning="Buy immediately.")
        mock_notify_fn = MagicMock()

        result = poll_all_items(
            engine, ebay, llm,
            notify_send_fn=mock_notify_fn,
            notify_recipient="owner@example.com",
        )

        assert result["notifications"] == 0
        mock_notify_fn.assert_not_called()
        # Confirm price drops WERE detected (the detection ran, just no notify)
        decisions = get_decisions_for_item(engine, 1)
        assert any(d["event_type"] == "price_drop_alert" for d in decisions)

    def test_public_alerts_fire_for_all_items(self, engine):
        from resale_price_agent.db import create_alert
        get_or_create_tracked_item(engine, "Jordan 4", owner="me")
        get_or_create_tracked_item(engine, "Public Item")  # no owner

        # Create public subscriptions for both items
        create_alert(engine, "subscriber@test.com", 1, "price_below:9999")
        create_alert(engine, "subscriber@test.com", 2, "price_below:9999")

        ebay = _MockEbay([_listing(item_id="v1|1|0", price=50.0)])
        llm = _MockLLM()
        mock_send = MagicMock()

        result = poll_all_items(engine, ebay, llm, send_fn=mock_send)

        assert result["alerts_sent"] == 2
        # Both calls go to the subscriber, not to NOTIFY_TO
        for call in mock_send.call_args_list:
            assert call[0][0] == "subscriber@test.com"

    def test_seeded_item_never_triggers_personal_notify(self, engine):
        seed_tracked_item(engine, "PS5 Console")  # seeded, no owner
        _seed_history(engine, 1, [200.0] * 6)

        ebay = _MockEbay([_listing(item_id="v1|cheap|0", price=100.0)])
        llm = _MockLLM(action="buy_now", confidence=0.9, reasoning="Deal.")
        mock_notify_fn = MagicMock()

        result = poll_all_items(
            engine, ebay, llm,
            notify_send_fn=mock_notify_fn,
            notify_recipient="owner@example.com",
        )

        assert result["notifications"] == 0
        mock_notify_fn.assert_not_called()


# ---------------------------------------------------------------------------
# Outlier filtering
# ---------------------------------------------------------------------------

class TestOutlierFilter:
    def test_drops_outliers_below_floor(self, engine):
        """Listings priced far below the rolling median are dropped."""
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0] * 6)

        new_snaps = [
            {"price": 10.0, "title": "Phone case"},
            {"price": 15.0, "title": "Screen protector"},
            {"price": 180.0, "title": "Real item"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        assert len(result) == 1
        assert result[0]["title"] == "Real item"

    def test_skips_filter_when_not_enough_history_or_batch(self, engine):
        """With too few history AND too few batch items, nothing filtered."""
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "New Item")
        _seed_history(engine, item["id"], [200.0, 210.0])

        # Only 2 history + 2 batch items — below both thresholds
        new_snaps = [
            {"price": 10.0, "title": "Cheap thing"},
            {"price": 180.0, "title": "Normal thing"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        assert len(result) == 2

    def test_keeps_legitimate_low_prices(self, engine):
        """Prices above the floor ratio are kept."""
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item["id"], [200.0] * 6)

        new_snaps = [
            {"price": 85.0, "title": "Legit deal"},
            {"price": 200.0, "title": "Normal price"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        assert len(result) == 2

    def test_empty_input_returns_empty(self, engine):
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        assert filter_outliers(engine, item["id"], []) == []

    def test_cold_start_drops_accessory_outlier(self, engine):
        """On cold start (no history), batch median filter catches
        extreme outliers like a screen protector among real phones.

        Regression test for Samsung Galaxy Z Flip 5 contamination:
        $27 screen protector surviving first poll alongside $86+ phones.
        """
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "Samsung Galaxy Z Flip 5")
        # No history at all — cold start

        # Simulate realistic batch: 1 accessory, rest are phones
        new_snaps = [
            {"price": 27.36, "title": "Screen Protector for Z Flip 5"},
            {"price": 86.0, "title": "Z Flip 5 broken screen"},
            {"price": 130.0, "title": "Z Flip 5 256GB unlocked"},
            {"price": 200.0, "title": "Z Flip 5 256GB mint"},
            {"price": 250.0, "title": "Z Flip 5 512GB"},
            {"price": 300.0, "title": "Z Flip 5 512GB new"},
            {"price": 350.0, "title": "Z Flip 5 512GB sealed"},
            {"price": 400.0, "title": "Z Flip 5 512GB sealed"},
            {"price": 450.0, "title": "Z Flip 5 1TB new"},
            {"price": 500.0, "title": "Z Flip 5 1TB sealed"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        # Batch median is ~275, floor is 275 * 0.4 = 110
        # Screen protector ($27.36) and broken phone ($86) dropped
        titles = [s["title"] for s in result]
        assert "Screen Protector for Z Flip 5" not in titles
        assert "Z Flip 5 256GB unlocked" in titles
        assert len(result) >= 8

    def test_cold_start_skips_small_batch(self, engine):
        """Cold-start filter doesn't activate with too few listings.

        Regression test: MTG MH3 Collector Box with only 2 listings
        should keep both, even if prices vary wildly.
        """
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "MTG MH3 Collector Box")
        # No history, only 2 listings
        new_snaps = [
            {"price": 10.0, "title": "Cheap listing"},
            {"price": 125.0, "title": "Expensive listing"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        assert len(result) == 2

    def test_cold_start_keeps_uniform_cheap_items(self, engine):
        """Items that are legitimately cheap (e.g. tumblers at $30-50)
        should not have listings stripped by the batch filter."""
        from resale_price_agent.poller import filter_outliers

        item, _, _ = get_or_create_tracked_item(engine, "Stanley Tumbler")
        new_snaps = [
            {"price": 25.0, "title": "Stanley 40oz"},
            {"price": 30.0, "title": "Stanley 40oz"},
            {"price": 32.0, "title": "Stanley 40oz"},
            {"price": 35.0, "title": "Stanley 40oz"},
            {"price": 38.0, "title": "Stanley 40oz"},
            {"price": 40.0, "title": "Stanley 40oz"},
            {"price": 42.0, "title": "Stanley 40oz"},
            {"price": 45.0, "title": "Stanley 40oz"},
        ]
        result = filter_outliers(engine, item["id"], new_snaps)

        # Median ~36.5, floor ~14.6 — all kept
        assert len(result) == 8


# ---------------------------------------------------------------------------
# Category ID passthrough
# ---------------------------------------------------------------------------

class TestCategoryFiltering:
    def test_category_id_passed_to_ebay(self, engine):
        """ebay_category_id from tracked_item flows to search_listings."""
        from resale_price_agent.db import seed_tracked_item

        seed_tracked_item(engine, "Samsung Galaxy Z Flip 5",
                          ebay_category_id="9355")
        items = get_all_tracked_items(engine)
        assert items[0]["ebay_category_id"] == "9355"

        class _TrackingEbay:
            def __init__(self):
                self.calls = []
            def search_listings(self, query, limit=50, category_ids=None):
                self.calls.append({"query": query, "category_ids": category_ids})
                return [_listing()]

        ebay = _TrackingEbay()
        poll_all_items(engine, ebay, _MockLLM())

        assert ebay.calls[0]["category_ids"] == "9355"

    def test_no_category_id_passes_none(self, engine):
        """Items without ebay_category_id pass None to search_listings."""
        get_or_create_tracked_item(engine, "Some item")

        class _TrackingEbay:
            def __init__(self):
                self.calls = []
            def search_listings(self, query, limit=50, category_ids=None):
                self.calls.append({"category_ids": category_ids})
                return [_listing()]

        ebay = _TrackingEbay()
        poll_all_items(engine, ebay, _MockLLM())

        assert ebay.calls[0]["category_ids"] is None

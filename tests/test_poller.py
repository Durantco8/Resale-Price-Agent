"""Tests for the polling script — faked eBay client, in-memory DB."""

import pytest
from sqlalchemy import create_engine

from poller import poll_once, snapshot_to_dict
from resale_price_agent.db import (
    add_tracked_item,
    get_snapshots_for_item,
    metadata,
    set_tracked_item_active,
)
from resale_price_agent.ebay_client import ListingSnapshot


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


def _make_listing(**overrides):
    defaults = {
        "item_id": "v1|111|0",
        "title": "Jordan 4 Military Black",
        "price_amount": 219.99,
        "price_currency": "USD",
        "condition": "New with box",
        "seller_feedback_score": 5000,
        "item_url": "https://www.ebay.com/itm/111",
        "shipping_cost": 14.95,
        "item_location": "Portland, OR, US",
        "buying_options": ["FIXED_PRICE"],
        "snapshot_time": "2026-08-30T12:00:00.000Z",
    }
    defaults.update(overrides)
    return ListingSnapshot(**defaults)


class FakeEbayClient:
    """Controllable fake — returns preset results or raises per query."""

    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def search_listings(self, query, limit=50):
        self.calls.append(query)
        result = self._responses.get(query)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else []


# ---------------------------------------------------------------------------
# snapshot_to_dict
# ---------------------------------------------------------------------------

class TestSnapshotToDict:
    def test_converts_all_fields(self):
        listing = _make_listing()
        d = snapshot_to_dict(listing)

        assert d["ebay_item_id"] == "v1|111|0"
        assert d["title"] == "Jordan 4 Military Black"
        assert d["price"] == 219.99
        assert d["currency"] == "USD"
        assert d["condition"] == "New with box"
        assert d["seller_feedback_score"] == 5000
        assert d["shipping_cost"] == 14.95
        assert d["item_location"] == "Portland, OR, US"
        assert d["buying_format"] == "FIXED_PRICE"
        assert d["item_url"] == "https://www.ebay.com/itm/111"

    def test_multiple_buying_options(self):
        listing = _make_listing(buying_options=["FIXED_PRICE", "BEST_OFFER"])
        d = snapshot_to_dict(listing)
        assert d["buying_format"] == "FIXED_PRICE, BEST_OFFER"

    def test_empty_buying_options(self):
        listing = _make_listing(buying_options=[])
        d = snapshot_to_dict(listing)
        assert d["buying_format"] is None


# ---------------------------------------------------------------------------
# poll_once
# ---------------------------------------------------------------------------

class TestPollOnce:
    def test_no_active_items(self, engine):
        fake = FakeEbayClient()
        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 0
        assert result["failed"] == 0
        assert result["total_listings"] == 0
        assert fake.calls == []

    def test_single_item_with_listings(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4 size 10")
        fake = FakeEbayClient(responses={
            "Jordan 4 size 10": [
                _make_listing(item_id="v1|111|0", price_amount=219.99),
                _make_listing(item_id="v1|222|0", price_amount=205.00),
            ],
        })

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 1
        assert result["failed"] == 0
        assert result["total_listings"] == 2
        assert len(get_snapshots_for_item(engine, item_id)) == 2

    def test_multiple_items(self, engine):
        id_a = add_tracked_item(engine, "Item A")
        id_b = add_tracked_item(engine, "Item B")
        fake = FakeEbayClient(responses={
            "Item A": [_make_listing(item_id="v1|aaa|0")],
            "Item B": [
                _make_listing(item_id="v1|bbb|0"),
                _make_listing(item_id="v1|ccc|0"),
            ],
        })

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 2
        assert result["total_listings"] == 3
        assert len(get_snapshots_for_item(engine, id_a)) == 1
        assert len(get_snapshots_for_item(engine, id_b)) == 2

    def test_paused_items_skipped(self, engine):
        id_a = add_tracked_item(engine, "Active item")
        id_b = add_tracked_item(engine, "Paused item")
        set_tracked_item_active(engine, id_b, False)

        fake = FakeEbayClient(responses={
            "Active item": [_make_listing()],
            "Paused item": [_make_listing()],
        })

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 1
        assert fake.calls == ["Active item"]

    def test_item_with_no_results(self, engine):
        add_tracked_item(engine, "Rare item nobody has")
        fake = FakeEbayClient(responses={"Rare item nobody has": []})

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 1
        assert result["total_listings"] == 0

    def test_failure_isolation(self, engine):
        """One item's API failure must not prevent the others from polling."""
        id_a = add_tracked_item(engine, "Good item")
        id_b = add_tracked_item(engine, "Bad item")
        id_c = add_tracked_item(engine, "Also good")

        fake = FakeEbayClient(responses={
            "Good item": [_make_listing(item_id="v1|aaa|0")],
            "Bad item": ConnectionError("eBay API timeout"),
            "Also good": [_make_listing(item_id="v1|ccc|0")],
        })

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 2
        assert result["failed"] == 1
        assert result["total_listings"] == 2
        assert len(get_snapshots_for_item(engine, id_a)) == 1
        assert len(get_snapshots_for_item(engine, id_b)) == 0
        assert len(get_snapshots_for_item(engine, id_c)) == 1

    def test_all_items_fail(self, engine):
        add_tracked_item(engine, "Fail A")
        add_tracked_item(engine, "Fail B")

        fake = FakeEbayClient(responses={
            "Fail A": RuntimeError("rate limited"),
            "Fail B": TimeoutError("timed out"),
        })

        result = poll_once(engine=engine, ebay_client=fake)

        assert result["processed"] == 0
        assert result["failed"] == 2
        assert result["total_listings"] == 0

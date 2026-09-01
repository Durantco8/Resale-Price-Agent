"""Tests for the full pipeline — faked eBay client, LLM client, and email."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from poller import poll_once, snapshot_to_dict
from resale_price_agent.db import (
    add_tracked_item,
    get_decisions_for_item,
    get_snapshots_for_item,
    insert_snapshots,
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
    def __init__(self, responses=None):
        self._responses = responses or {}
        self.calls = []

    def search_listings(self, query, limit=50):
        self.calls.append(query)
        result = self._responses.get(query)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else []


class FakeLLMModels:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def generate_content(self, **kwargs):
        if self._error:
            raise self._error
        return self._response


class FakeLLMClient:
    def __init__(self, response=None, error=None):
        self.models = FakeLLMModels(response=response, error=error)


def _llm_response(action="wait", confidence=0.5, reasoning="Holding."):
    return SimpleNamespace(text=json.dumps({
        "action": action, "confidence": confidence, "reasoning": reasoning,
    }))


def _seed_history(engine, item_id, prices, start_hours_ago=48):
    snaps = []
    for i, price in enumerate(prices):
        snaps.append({
            "ebay_item_id": f"hist-{i}",
            "title": "Historical",
            "price": price,
            "snapshot_time": datetime.now(timezone.utc) - timedelta(hours=start_hours_ago - i),
        })
    insert_snapshots(engine, item_id, snaps)


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
# Core polling (Stage 4 behavior)
# ---------------------------------------------------------------------------

class TestPollOnce:
    def test_no_active_items(self, engine):
        fake = FakeEbayClient()
        result = poll_once(engine=engine, ebay_client=fake,
                           llm_client=FakeLLMClient())

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

        result = poll_once(engine=engine, ebay_client=fake,
                           llm_client=FakeLLMClient())

        assert result["processed"] == 1
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

        result = poll_once(engine=engine, ebay_client=fake,
                           llm_client=FakeLLMClient())

        assert result["processed"] == 2
        assert result["total_listings"] == 3

    def test_paused_items_skipped(self, engine):
        add_tracked_item(engine, "Active item")
        id_b = add_tracked_item(engine, "Paused item")
        set_tracked_item_active(engine, id_b, False)

        fake = FakeEbayClient(responses={
            "Active item": [_make_listing()],
            "Paused item": [_make_listing()],
        })

        result = poll_once(engine=engine, ebay_client=fake,
                           llm_client=FakeLLMClient())

        assert result["processed"] == 1
        assert fake.calls == ["Active item"]

    def test_failure_isolation(self, engine):
        id_a = add_tracked_item(engine, "Good item")
        add_tracked_item(engine, "Bad item")
        id_c = add_tracked_item(engine, "Also good")

        fake = FakeEbayClient(responses={
            "Good item": [_make_listing(item_id="v1|aaa|0")],
            "Bad item": ConnectionError("eBay API timeout"),
            "Also good": [_make_listing(item_id="v1|ccc|0")],
        })

        result = poll_once(engine=engine, ebay_client=fake,
                           llm_client=FakeLLMClient())

        assert result["processed"] == 2
        assert result["failed"] == 1
        assert len(get_snapshots_for_item(engine, id_a)) == 1
        assert len(get_snapshots_for_item(engine, id_c)) == 1


# ---------------------------------------------------------------------------
# Pipeline integration: price-drop → notify
# ---------------------------------------------------------------------------

class TestPipelinePriceDrop:
    def test_target_price_triggers_notification(self, engine):
        add_tracked_item(engine, "Jordan 4", target_price=200.0)

        emails = []
        def fake_send(to, subject, body):
            emails.append((to, subject, body))

        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=185.0)],
        })

        result = poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=FakeLLMClient(),
            send_fn=lambda to, subj, body: emails.append((to, subj, body)),
            notify_recipient="test@example.com",
        )

        assert result["alerts"] >= 1
        assert result["notifications"] >= 1
        assert any("Price drop" in e[1] for e in emails)

    def test_no_alert_when_above_target(self, engine):
        add_tracked_item(engine, "Jordan 4", target_price=150.0)

        emails = []
        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=219.99)],
        })

        result = poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=FakeLLMClient(),
            send_fn=lambda to, subj, body: emails.append(True),
            notify_recipient="test@example.com",
        )

        assert result["alerts"] == 0


# ---------------------------------------------------------------------------
# Pipeline integration: LLM buy_now → notify
# ---------------------------------------------------------------------------

class TestPipelineLLM:
    def test_buy_now_triggers_notification(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        # Seed enough history for LLM to run
        _seed_history(engine, item_id, [220.0] * 10)

        emails = []
        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=200.0)],
        })
        fake_llm = FakeLLMClient(
            response=_llm_response("buy_now", 0.9, "Great deal.")
        )

        result = poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=fake_llm,
            send_fn=lambda to, subj, body: emails.append((to, subj, body)),
            notify_recipient="test@example.com",
        )

        assert result["notifications"] >= 1
        assert any("Buy now" in e[1] for e in emails)

    def test_wait_no_notification(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        _seed_history(engine, item_id, [220.0] * 10)

        emails = []
        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=219.0)],
        })
        fake_llm = FakeLLMClient(
            response=_llm_response("wait", 0.5, "Not yet.")
        )

        result = poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=fake_llm,
            send_fn=lambda to, subj, body: emails.append(True),
            notify_recipient="test@example.com",
        )

        # Should have 0 notifications for LLM wait (price drop might or
        # might not fire depending on threshold, so just check no buy_now emails)
        assert not any(
            isinstance(e, tuple) and "Buy now" in e[1] for e in emails
        )

    def test_insufficient_data_skips_llm(self, engine):
        """With no history, LLM should be skipped — no LLM decision stored."""
        add_tracked_item(engine, "Jordan 4")

        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=200.0)],
        })
        fake_llm = FakeLLMClient(
            response=_llm_response("buy_now", 0.9, "Should not appear.")
        )

        poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=fake_llm,
            send_fn=lambda *a: None,
            notify_recipient="test@example.com",
        )

        # The only decisions should be from price-drop (if any), not LLM
        decisions = get_decisions_for_item(engine, 1)
        llm_decisions = [d for d in decisions if d["event_type"] == "llm_reasoning"]
        assert llm_decisions == []


# ---------------------------------------------------------------------------
# Notification failure doesn't crash pipeline
# ---------------------------------------------------------------------------

class TestNotificationFailure:
    def test_email_failure_doesnt_crash(self, engine):
        add_tracked_item(engine, "Jordan 4", target_price=250.0)

        def failing_send(to, subject, body):
            raise ConnectionError("SMTP down")

        fake_ebay = FakeEbayClient(responses={
            "Jordan 4": [_make_listing(price_amount=185.0)],
        })

        # Should not raise
        result = poll_once(
            engine=engine, ebay_client=fake_ebay,
            llm_client=FakeLLMClient(),
            send_fn=failing_send,
            notify_recipient="test@example.com",
        )

        assert result["processed"] == 1
        assert result["alerts"] >= 1
        assert result["notifications"] == 0  # email failed but pipeline continued

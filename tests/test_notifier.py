"""Tests for the email notification module."""

import json

import pytest

from resale_price_agent.notifier import notify


def _price_drop_decision(**overrides):
    signals = {
        "listing_price": 185.0,
        "ebay_item_id": "v1|111|0",
        "title": "Jordan 4 Military Black",
        "item_url": "https://www.ebay.com/itm/111",
        "rolling_avg": 220.0,
        "pct_below_avg": 15.9,
        "target_price": 200.0,
    }
    signals.update(overrides.pop("signals_override", {}))
    d = {
        "id": 1,
        "event_type": "price_drop_alert",
        "action": None,
        "confidence": None,
        "reasoning": "$185.00 is at or below target price $200.00; $185.00 is 15.9% below 14-day average $220.00",
        "computed_signals": json.dumps(signals),
    }
    d.update(overrides)
    return d


def _buy_now_decision(**overrides):
    signals = {
        "sufficient_data": True,
        "avg_price": 200.0,
        "min_price": 180.0,
        "max_price": 220.0,
        "price_trend": "falling",
        "price_trend_pct": -5.0,
        "listing_trend": "rising",
        "listing_trend_pct": 10.0,
    }
    d = {
        "id": 2,
        "event_type": "llm_reasoning",
        "action": "buy_now",
        "confidence": 0.85,
        "reasoning": "Prices falling with rising supply — good time to buy.",
        "computed_signals": json.dumps(signals),
    }
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# Should send
# ---------------------------------------------------------------------------

class TestShouldSend:
    def test_price_drop_sends(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append((to, subject, body))

        result = notify(
            "Jordan 4 size 10", _price_drop_decision(),
            send_fn=fake_send, recipient="test@example.com",
        )

        assert result is True
        assert len(sent) == 1
        assert "Price drop alert" in sent[0][1]
        assert "$185.0" in sent[0][2]
        assert "target price" in sent[0][2]
        assert "ebay.com" in sent[0][2]

    def test_buy_now_sends(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append((to, subject, body))

        result = notify(
            "Jordan 4 size 10", _buy_now_decision(),
            send_fn=fake_send, recipient="test@example.com",
        )

        assert result is True
        assert len(sent) == 1
        assert "Buy now" in sent[0][1]
        assert "0.85" in sent[0][2]
        assert "falling" in sent[0][2].lower()

    def test_email_body_includes_reasoning(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append(body)

        notify(
            "Jordan 4 size 10", _buy_now_decision(),
            send_fn=fake_send, recipient="test@example.com",
        )

        assert "Prices falling with rising supply" in sent[0]


# ---------------------------------------------------------------------------
# Should NOT send
# ---------------------------------------------------------------------------

class TestShouldNotSend:
    def test_wait_decision_no_email(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append(True)

        result = notify(
            "Jordan 4", {"event_type": "llm_reasoning", "action": "wait"},
            send_fn=fake_send, recipient="test@example.com",
        )

        assert result is False
        assert sent == []

    def test_skip_decision_no_email(self):
        result = notify(
            "Jordan 4", {"event_type": "llm_reasoning", "action": "skip"},
            send_fn=lambda *a: None, recipient="test@example.com",
        )

        assert result is False

    def test_no_recipient_no_email(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append(True)

        result = notify(
            "Jordan 4", _price_drop_decision(),
            send_fn=fake_send, recipient="",
        )

        assert result is False
        assert sent == []


# ---------------------------------------------------------------------------
# Send failure
# ---------------------------------------------------------------------------

class TestSendFailure:
    def test_smtp_error_returns_false(self):
        def failing_send(to, subject, body):
            raise ConnectionError("SMTP connection refused")

        result = notify(
            "Jordan 4", _price_drop_decision(),
            send_fn=failing_send, recipient="test@example.com",
        )

        assert result is False

    def test_timeout_returns_false(self):
        def timeout_send(to, subject, body):
            raise TimeoutError("SMTP timeout")

        result = notify(
            "Jordan 4", _buy_now_decision(),
            send_fn=timeout_send, recipient="test@example.com",
        )

        assert result is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_signals_fields(self):
        """Email should still send even if some signal fields are missing."""
        sent = []
        def fake_send(to, subject, body):
            sent.append(body)

        decision = _price_drop_decision(
            computed_signals=json.dumps({"listing_price": 150.0}),
        )
        result = notify(
            "Jordan 4", decision,
            send_fn=fake_send, recipient="test@example.com",
        )

        assert result is True
        assert "$150.0" in sent[0]

    def test_empty_computed_signals(self):
        sent = []
        def fake_send(to, subject, body):
            sent.append(body)

        decision = _price_drop_decision(computed_signals="{}")
        result = notify(
            "Jordan 4", decision,
            send_fn=fake_send, recipient="test@example.com",
        )

        assert result is True

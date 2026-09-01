"""Tests for alert matching, email sending, and unsubscribe."""

import pytest

from resale_price_agent.alerts import match_alerts, process_alerts, send_alert_email
from resale_price_agent.db import (
    create_alert,
    get_active_alerts_for_item,
    get_or_create_tracked_item,
    unsubscribe_by_token,
)
from resale_price_agent.llm_reasoning import LLMDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(price=200.0, **kw):
    defaults = {"ebay_item_id": "v1|123|0", "title": "Test", "price": price}
    defaults.update(kw)
    return defaults


def _decision(action="wait", confidence=0.5, reasoning="Holding.",
              skipped=False, skip_reason=None):
    return LLMDecision(
        action=action, confidence=confidence, reasoning=reasoning,
        skipped=skipped, skip_reason=skip_reason,
    )


def _alert_dict(condition="buy_now", email="a@b.com", alert_id=1, token="tok123"):
    return {
        "id": alert_id,
        "email": email,
        "condition": condition,
        "active": True,
        "unsubscribe_token": token,
        "tracked_item_id": 1,
    }


class FakeSender:
    """Records sent emails without any network calls."""

    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def __call__(self, to, subject, body):
        self.sent.append((to, subject, body))


class FailingSender:
    def __call__(self, to, subject, body):
        raise ConnectionError("SMTP down")


# ---------------------------------------------------------------------------
# Price threshold matching
# ---------------------------------------------------------------------------

class TestPriceThreshold:
    def test_fires_below_threshold(self):
        alerts = [_alert_dict(condition="price_below:200.00")]
        matched = match_alerts(alerts, [_snap(price=185.0)], None)
        assert len(matched) == 1
        assert "185.00" in matched[0][1]
        assert "200.00" in matched[0][1]

    def test_fires_at_threshold(self):
        alerts = [_alert_dict(condition="price_below:200.00")]
        matched = match_alerts(alerts, [_snap(price=200.0)], None)
        assert len(matched) == 1

    def test_does_not_fire_above_threshold(self):
        alerts = [_alert_dict(condition="price_below:200.00")]
        matched = match_alerts(alerts, [_snap(price=200.01)], None)
        assert len(matched) == 0

    def test_fires_if_any_snapshot_matches(self):
        """Multiple snapshots — only one needs to be below threshold."""
        alerts = [_alert_dict(condition="price_below:180.00")]
        snaps = [_snap(price=210.0), _snap(price=175.0), _snap(price=195.0)]
        matched = match_alerts(alerts, snaps, None)
        assert len(matched) == 1

    def test_no_double_fire_on_multiple_matching_snapshots(self):
        """If multiple snapshots match, the alert fires once, not per-snapshot."""
        alerts = [_alert_dict(condition="price_below:200.00")]
        snaps = [_snap(price=190.0), _snap(price=185.0)]
        matched = match_alerts(alerts, snaps, None)
        assert len(matched) == 1

    def test_empty_snapshots_no_fire(self):
        alerts = [_alert_dict(condition="price_below:200.00")]
        matched = match_alerts(alerts, [], None)
        assert len(matched) == 0


# ---------------------------------------------------------------------------
# Buy now matching
# ---------------------------------------------------------------------------

class TestBuyNowCondition:
    def test_fires_on_buy_now(self):
        alerts = [_alert_dict(condition="buy_now")]
        decision = _decision(action="buy_now", confidence=0.9, reasoning="Great deal.")
        matched = match_alerts(alerts, [_snap()], decision)
        assert len(matched) == 1
        assert "Buy now" in matched[0][1]
        assert "90%" in matched[0][1]

    def test_does_not_fire_on_wait(self):
        alerts = [_alert_dict(condition="buy_now")]
        decision = _decision(action="wait")
        matched = match_alerts(alerts, [_snap()], decision)
        assert len(matched) == 0

    def test_does_not_fire_on_skip(self):
        alerts = [_alert_dict(condition="buy_now")]
        decision = _decision(action="skip")
        matched = match_alerts(alerts, [_snap()], decision)
        assert len(matched) == 0

    def test_does_not_fire_on_skipped_decision(self):
        alerts = [_alert_dict(condition="buy_now")]
        decision = _decision(action="skip", skipped=True, skip_reason="insufficient_data")
        matched = match_alerts(alerts, [_snap()], decision)
        assert len(matched) == 0

    def test_does_not_fire_with_no_decision(self):
        alerts = [_alert_dict(condition="buy_now")]
        matched = match_alerts(alerts, [_snap()], None)
        assert len(matched) == 0


# ---------------------------------------------------------------------------
# Multiple alerts on the same item
# ---------------------------------------------------------------------------

class TestMultipleAlerts:
    def test_independent_evaluation(self):
        alerts = [
            _alert_dict(condition="price_below:190.00", email="a@b.com", alert_id=1),
            _alert_dict(condition="price_below:170.00", email="c@d.com", alert_id=2),
            _alert_dict(condition="buy_now", email="e@f.com", alert_id=3),
        ]
        snaps = [_snap(price=185.0)]
        decision = _decision(action="wait")

        matched = match_alerts(alerts, snaps, decision)

        # Only the first alert should fire (185 <= 190, but 185 > 170, and no buy_now)
        assert len(matched) == 1
        assert matched[0][0]["email"] == "a@b.com"

    def test_all_matching_alerts_fire(self):
        alerts = [
            _alert_dict(condition="price_below:200.00", email="a@b.com", alert_id=1),
            _alert_dict(condition="price_below:190.00", email="c@d.com", alert_id=2),
            _alert_dict(condition="buy_now", email="e@f.com", alert_id=3),
        ]
        snaps = [_snap(price=185.0)]
        decision = _decision(action="buy_now", confidence=0.85)

        matched = match_alerts(alerts, snaps, decision)

        # All three should fire
        assert len(matched) == 3
        emails = {m[0]["email"] for m in matched}
        assert emails == {"a@b.com", "c@d.com", "e@f.com"}


# ---------------------------------------------------------------------------
# Unknown condition
# ---------------------------------------------------------------------------

class TestUnknownCondition:
    def test_skipped_gracefully(self):
        alerts = [_alert_dict(condition="some_future_condition")]
        matched = match_alerts(alerts, [_snap()], _decision())
        assert len(matched) == 0

    def test_malformed_price_below(self):
        alerts = [_alert_dict(condition="price_below:not_a_number")]
        matched = match_alerts(alerts, [_snap(price=100.0)], None)
        assert len(matched) == 0


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

class TestSendAlertEmail:
    def test_sends_to_correct_email(self):
        sender = FakeSender()
        alert = _alert_dict(email="user@example.com")
        item = {"display_name": "Jordan 4", "search_query": "Jordan 4"}

        result = send_alert_email(alert, item, "Price dropped!", sender)

        assert result is True
        assert len(sender.sent) == 1
        assert sender.sent[0][0] == "user@example.com"

    def test_subject_includes_item_name(self):
        sender = FakeSender()
        alert = _alert_dict()
        item = {"display_name": "Nike Dunk Low Panda", "search_query": "Nike Dunk"}

        send_alert_email(alert, item, "Price dropped!", sender)

        assert "Nike Dunk Low Panda" in sender.sent[0][1]

    def test_body_includes_unsubscribe_token(self):
        sender = FakeSender()
        alert = _alert_dict(token="abc123def456")
        item = {"display_name": "Jordan 4", "search_query": "Jordan 4"}

        send_alert_email(alert, item, "Price dropped!", sender)

        assert "abc123def456" in sender.sent[0][2]

    def test_send_failure_returns_false(self):
        alert = _alert_dict()
        item = {"display_name": "Jordan 4", "search_query": "Jordan 4"}

        result = send_alert_email(alert, item, "Price dropped!", FailingSender())

        assert result is False


# ---------------------------------------------------------------------------
# process_alerts integration (with DB)
# ---------------------------------------------------------------------------

class TestProcessAlerts:
    def test_sends_matching_alerts(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        create_alert(engine, "user@example.com", item["id"], "price_below:200.00")

        sender = FakeSender()
        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, sender,
        )

        assert sent == 1
        assert len(sender.sent) == 1
        assert sender.sent[0][0] == "user@example.com"

    def test_no_alerts_no_emails(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

        sender = FakeSender()
        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, sender,
        )

        assert sent == 0
        assert sender.sent == []

    def test_non_matching_alerts_no_emails(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        create_alert(engine, "user@example.com", item["id"], "price_below:150.00")

        sender = FakeSender()
        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, sender,
        )

        assert sent == 0

    def test_send_failure_counted_correctly(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        create_alert(engine, "user@example.com", item["id"], "price_below:200.00")

        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, FailingSender(),
        )

        assert sent == 0  # failed to send


# ---------------------------------------------------------------------------
# Unsubscribe
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_unsubscribe_deactivates(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(engine, "a@b.com", item["id"], "buy_now")

        result = unsubscribe_by_token(engine, alert["unsubscribe_token"])
        assert result is True

        active = get_active_alerts_for_item(engine, item["id"])
        assert len(active) == 0

    def test_unsubscribed_alert_doesnt_fire(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(engine, "a@b.com", item["id"], "price_below:200.00")
        unsubscribe_by_token(engine, alert["unsubscribe_token"])

        sender = FakeSender()
        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, sender,
        )

        assert sent == 0
        assert sender.sent == []

    def test_invalid_token_returns_false(self, engine):
        result = unsubscribe_by_token(engine, "nonexistent_token")
        assert result is False

    def test_unsubscribe_only_affects_one_alert(self, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
        a1 = create_alert(engine, "a@b.com", item["id"], "price_below:200.00")
        create_alert(engine, "c@d.com", item["id"], "price_below:200.00")

        unsubscribe_by_token(engine, a1["unsubscribe_token"])

        sender = FakeSender()
        sent = process_alerts(
            engine, item, [_snap(price=185.0)], None, sender,
        )

        assert sent == 1
        assert sender.sent[0][0] == "c@d.com"

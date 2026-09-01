"""Tests for the LLM reasoning layer — all API calls faked."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from resale_price_agent.db import (
    add_tracked_item,
    get_decisions_for_item,
    metadata,
)
from resale_price_agent.llm_reasoning import (
    LLMDecision,
    _parse_response,
    get_llm_decision,
)
from resale_price_agent.signals import TrendSignals


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


# ---------------------------------------------------------------------------
# Helpers for faking Claude responses
# ---------------------------------------------------------------------------

def _tool_block(action="wait", confidence=0.7, reasoning="Prices are stable."):
    return SimpleNamespace(
        type="tool_use",
        name="record_decision",
        input={"action": action, "confidence": confidence, "reasoning": reasoning},
    )


def _make_response(*content_blocks):
    return SimpleNamespace(content=list(content_blocks))


class FakeClient:
    """Drop-in fake for anthropic.Anthropic — records calls, returns preset."""

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []
        self.messages = self  # client.messages.create(...)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def _sufficient_signals(**overrides):
    defaults = dict(
        sufficient_data=True,
        avg_price=200.0,
        min_price=180.0,
        max_price=220.0,
        snapshot_count=20,
        price_trend="falling",
        price_trend_pct=-5.0,
        listing_trend="rising",
        listing_trend_pct=10.0,
        window_days=14,
    )
    defaults.update(overrides)
    return TrendSignals(**defaults)


def _insufficient_signals():
    return TrendSignals(
        sufficient_data=False,
        avg_price=None,
        min_price=None,
        max_price=None,
        snapshot_count=3,
        price_trend=None,
        price_trend_pct=None,
        listing_trend=None,
        listing_trend_pct=None,
        window_days=14,
    )


# ---------------------------------------------------------------------------
# Insufficient data — LLM not called
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_skips_llm_call(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        fake = FakeClient()

        result = get_llm_decision(
            engine, item_id, _insufficient_signals(), "no listings", client=fake,
        )

        assert result.skipped is True
        assert result.skip_reason == "insufficient_data"
        assert result.action == "skip"
        assert fake.calls == []  # LLM was never called

    def test_no_decision_stored(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")

        get_llm_decision(
            engine, item_id, _insufficient_signals(), "no listings",
            client=FakeClient(),
        )

        assert get_decisions_for_item(engine, item_id) == []


# ---------------------------------------------------------------------------
# Valid responses
# ---------------------------------------------------------------------------

class TestValidResponse:
    def test_buy_now(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("buy_now", 0.9, "Prices dropping, high supply.")
        )
        fake = FakeClient(response=resp)

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "5 listings avg $195",
            client=fake,
        )

        assert result.action == "buy_now"
        assert result.confidence == 0.9
        assert result.reasoning == "Prices dropping, high supply."
        assert result.skipped is False

    def test_wait(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("wait", 0.6, "Trend unclear.")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "3 listings",
            client=FakeClient(response=resp),
        )

        assert result.action == "wait"
        assert result.confidence == 0.6

    def test_skip(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("skip", 0.3, "Not worth tracking.")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "1 listing",
            client=FakeClient(response=resp),
        )

        assert result.action == "skip"

    def test_decision_stored_in_db(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("buy_now", 0.85, "Great price.")
        )

        get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        decisions = get_decisions_for_item(engine, item_id)
        assert len(decisions) == 1
        d = decisions[0]
        assert d["event_type"] == "llm_reasoning"
        assert d["action"] == "buy_now"
        assert d["confidence"] == 0.85
        assert d["reasoning"] == "Great price."
        signals = json.loads(d["computed_signals"])
        assert signals["avg_price"] == 200.0

    def test_signals_forwarded_to_api(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(_tool_block())
        fake = FakeClient(response=resp)

        get_llm_decision(
            engine, item_id, _sufficient_signals(), "listing summary",
            client=fake,
        )

        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["model"] is not None
        user_msg = call["messages"][0]["content"]
        assert "avg_price" in user_msg
        assert "listing summary" in user_msg


# ---------------------------------------------------------------------------
# Malformed responses
# ---------------------------------------------------------------------------

class TestMalformedResponse:
    def test_invalid_action(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("hold", 0.5, "Invalid action value.")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True
        assert result.skip_reason == "parse_error"
        assert get_decisions_for_item(engine, item_id) == []

    def test_confidence_out_of_range(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("buy_now", 1.5, "Too confident.")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True
        assert result.skip_reason == "parse_error"

    def test_negative_confidence(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("wait", -0.1, "Negative confidence.")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True

    def test_empty_reasoning(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = _make_response(
            _tool_block("wait", 0.5, "")
        )

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True

    def test_missing_tool_use_block(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        text_block = SimpleNamespace(type="text", text="I think you should wait.")
        resp = _make_response(text_block)

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True
        assert result.skip_reason == "parse_error"

    def test_wrong_tool_name(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        block = SimpleNamespace(
            type="tool_use",
            name="wrong_tool",
            input={"action": "buy_now", "confidence": 0.8, "reasoning": "test"},
        )
        resp = _make_response(block)

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True

    def test_completely_garbled_response(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        resp = SimpleNamespace(content=None)  # content isn't iterable

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=FakeClient(response=resp),
        )

        assert result.skipped is True
        assert result.skip_reason == "parse_error"


# ---------------------------------------------------------------------------
# API errors
# ---------------------------------------------------------------------------

class TestAPIErrors:
    def test_api_timeout(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        fake = FakeClient(error=TimeoutError("Request timed out"))

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=fake,
        )

        assert result.skipped is True
        assert result.skip_reason == "api_error"
        assert get_decisions_for_item(engine, item_id) == []

    def test_api_connection_error(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        fake = FakeClient(error=ConnectionError("Network unreachable"))

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=fake,
        )

        assert result.skipped is True
        assert result.skip_reason == "api_error"

    def test_api_rate_limit(self, engine):
        item_id = add_tracked_item(engine, "Jordan 4")
        fake = FakeClient(error=RuntimeError("rate_limit_error"))

        result = get_llm_decision(
            engine, item_id, _sufficient_signals(), "summary",
            client=fake,
        )

        assert result.skipped is True
        assert result.skip_reason == "api_error"


# ---------------------------------------------------------------------------
# _parse_response unit tests
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_valid(self):
        resp = _make_response(_tool_block("buy_now", 0.8, "Good price."))
        result = _parse_response(resp)

        assert result is not None
        assert result.action == "buy_now"

    def test_confidence_zero(self):
        resp = _make_response(_tool_block("skip", 0.0, "No idea."))
        result = _parse_response(resp)

        assert result is not None
        assert result.confidence == 0.0

    def test_confidence_one(self):
        resp = _make_response(_tool_block("buy_now", 1.0, "Certain."))
        result = _parse_response(resp)

        assert result is not None
        assert result.confidence == 1.0

    def test_integer_confidence(self):
        """Confidence of 1 (int) should be accepted."""
        resp = _make_response(_tool_block("wait", 1, "Sure."))
        result = _parse_response(resp)

        assert result is not None
        assert result.confidence == 1.0

    def test_none_on_empty_content(self):
        resp = _make_response()
        assert _parse_response(resp) is None

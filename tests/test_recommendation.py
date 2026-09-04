"""Tests for the deterministic recommendation engine — test-first.

Covers pure rule evaluation, idempotent storage, latest-recommendation
queries, and schema migration.  All DB tests use in-memory SQLite.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

from resale_price_agent.db import (
    decisions,
    get_or_create_tracked_item,
    insert_decision,
    metadata,
)
from resale_price_agent.recommendation import (
    RULESET_VERSION,
    Recommendation,
    _history_label,
    evaluate,
    get_latest_deterministic_recommendation,
    record_recommendation,
)
from resale_price_agent.signals import TrendSignals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signals(**overrides) -> TrendSignals:
    """Build a TrendSignals with sensible multi-batch defaults.

    Callers override only the fields they care about.
    """
    defaults = dict(
        sufficient_data=True,
        avg_price=100.0,
        min_price=80.0,
        max_price=120.0,
        snapshot_count=50,
        price_trend="flat",
        price_trend_pct=0.5,
        listing_trend="flat",
        listing_trend_pct=0.0,
        window_days=14,
        poll_batch_count=3,
        history_span_days=7.0,
        latest_batch_time="2026-09-03T15:00:00+00:00",
        freshness_hours=6.0,
        latest_batch_listing_count=50,
        latest_batch_median=100.0,
        historical_median=100.0,
        median_batch_price=100.0,
        price_p25=90.0,
        price_p75=110.0,
        price_iqr=20.0,
        unique_listing_count=95,
    )
    defaults.update(overrides)
    return TrendSignals(**defaults)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    # Partial unique index for idempotency — matches _migrate_schema logic
    with eng.begin() as conn:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_deterministic_rec "
            "ON decisions (tracked_item_id, source_poll_batch_id, "
            "ruleset_version) "
            "WHERE event_type = 'deterministic_recommendation'"
        ))
    return eng


def _create_item(engine, query="Test Item"):
    item, _, _ = get_or_create_tracked_item(engine, query)
    return item["id"]


# ===================================================================
# Category A: Pure Rule Evaluation (no DB)
# ===================================================================


class TestInsufficientData:
    """Gate 0 — insufficient history always produces low-confidence WAIT."""

    def test_insufficient_data_returns_wait(self):
        rec = evaluate(_signals(sufficient_data=False))
        assert rec.action == "wait"
        assert rec.confidence == pytest.approx(0.20)

    def test_insufficient_data_never_returns_buy(self):
        """Even with favorable prices, insufficient data blocks BUY."""
        rec = evaluate(_signals(
            sufficient_data=False,
            latest_batch_median=80.0,
            historical_median=100.0,
            price_trend="falling",
            listing_trend="rising",
        ))
        assert rec.action == "wait"

    def test_insufficient_data_never_returns_skip(self):
        """Even with alarm signals, insufficient data blocks SKIP."""
        rec = evaluate(_signals(
            sufficient_data=False,
            latest_batch_median=150.0,
            historical_median=100.0,
            price_trend="rising",
            price_trend_pct=20.0,
        ))
        assert rec.action == "wait"


class TestNullGuard:
    """Explicit null guard for required fields — defense in depth."""

    def test_null_latest_batch_median_returns_wait(self):
        rec = evaluate(_signals(
            sufficient_data=True,
            latest_batch_median=None,
        ))
        assert rec.action == "wait"
        assert rec.confidence == pytest.approx(0.20)

    def test_null_historical_median_returns_wait(self):
        rec = evaluate(_signals(
            sufficient_data=True,
            historical_median=None,
        ))
        assert rec.action == "wait"
        assert rec.confidence == pytest.approx(0.20)

    def test_null_freshness_returns_wait(self):
        rec = evaluate(_signals(
            sufficient_data=True,
            freshness_hours=None,
        ))
        assert rec.action == "wait"
        assert rec.confidence == pytest.approx(0.20)


class TestStaleData:
    """Gate 1 — stale data produces conservative WAIT."""

    def test_stale_data_returns_wait(self):
        rec = evaluate(_signals(freshness_hours=100.0))
        assert rec.action == "wait"
        assert rec.confidence == pytest.approx(0.25)

    def test_72h_boundary_not_stale(self):
        """Exactly 72h is not stale."""
        rec = evaluate(_signals(freshness_hours=72.0))
        assert rec.action != "wait" or rec.confidence != pytest.approx(0.25)


class TestBuyGate:
    """Gate 2 — BUY requires meaningful discount + non-rising prices."""

    def test_buy_at_10pct_discount(self):
        """Minimum BUY threshold: 10% discount."""
        rec = evaluate(_signals(
            latest_batch_median=90.0,
            historical_median=100.0,
            price_trend="falling",
        ))
        assert rec.action == "buy_now"
        assert rec.confidence >= 0.50

    def test_no_buy_at_9pct_discount(self):
        """9% discount is below threshold — normal fluctuation."""
        rec = evaluate(_signals(
            latest_batch_median=91.0,
            historical_median=100.0,
            price_trend="falling",
        ))
        assert rec.action != "buy_now"

    def test_no_buy_with_rising_prices(self):
        """Rising prices block BUY even with a large discount."""
        rec = evaluate(_signals(
            latest_batch_median=80.0,
            historical_median=100.0,
            price_trend="rising",
            price_trend_pct=5.0,
        ))
        assert rec.action != "buy_now"

    def test_buy_not_blocked_by_falling_supply(self):
        """Falling supply does NOT block BUY — key design decision."""
        rec = evaluate(_signals(
            latest_batch_median=85.0,
            historical_median=100.0,
            price_trend="falling",
            listing_trend="falling",
            listing_trend_pct=-15.0,
        ))
        assert rec.action == "buy_now"

    def test_buy_flat_price_trend_allowed(self):
        """Flat prices (not rising) allow BUY with sufficient discount."""
        rec = evaluate(_signals(
            latest_batch_median=88.0,
            historical_median=100.0,
            price_trend="flat",
        ))
        assert rec.action == "buy_now"

    def test_buy_confidence_scales_with_discount(self):
        """Deeper discounts increase confidence."""
        rec_10 = evaluate(_signals(
            latest_batch_median=90.0, historical_median=100.0,
            price_trend="falling",
        ))
        rec_20 = evaluate(_signals(
            latest_batch_median=80.0, historical_median=100.0,
            price_trend="falling",
        ))
        assert rec_20.confidence > rec_10.confidence

    def test_buy_confidence_scales_with_maturity(self):
        """More batches + longer history increase confidence."""
        rec_low = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling",
            poll_batch_count=2, history_span_days=2.0,
        ))
        rec_high = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling",
            poll_batch_count=5, history_span_days=10.0,
        ))
        assert rec_high.confidence > rec_low.confidence

    def test_buy_confidence_capped_at_090(self):
        """Maximum BUY confidence is 0.90 — never 1.0."""
        rec = evaluate(_signals(
            latest_batch_median=70.0, historical_median=100.0,
            price_trend="falling", listing_trend="rising",
            poll_batch_count=10, history_span_days=14.0,
        ))
        assert rec.action == "buy_now"
        assert rec.confidence == pytest.approx(0.90)

    def test_buy_falling_supply_reduces_confidence(self):
        """Falling supply slightly reduces BUY confidence but doesn't block."""
        rec_flat = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling", listing_trend="flat",
        ))
        rec_falling = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling", listing_trend="falling",
            listing_trend_pct=-10.0,
        ))
        assert rec_falling.confidence < rec_flat.confidence


class TestSkipGate:
    """Gate 3 — SKIP requires strong negative pricing evidence."""

    def test_skip_materially_overpriced(self):
        """20%+ above historical median triggers SKIP."""
        rec = evaluate(_signals(
            latest_batch_median=125.0,
            historical_median=100.0,
            price_trend="rising",
            price_trend_pct=5.0,
        ))
        assert rec.action == "skip"

    def test_skip_strong_rising_prices(self):
        """15%+ rising price trend triggers SKIP."""
        rec = evaluate(_signals(
            latest_batch_median=110.0,
            historical_median=100.0,
            price_trend="rising",
            price_trend_pct=16.0,
        ))
        assert rec.action == "skip"

    def test_no_skip_from_falling_supply_alone(self):
        """Falling supply alone never triggers SKIP."""
        rec = evaluate(_signals(
            latest_batch_median=100.0,
            historical_median=100.0,
            listing_trend="falling",
            listing_trend_pct=-25.0,
        ))
        assert rec.action != "skip"

    def test_skip_both_conditions_higher_confidence(self):
        """Both SKIP conditions firing increases confidence."""
        rec_one = evaluate(_signals(
            latest_batch_median=125.0, historical_median=100.0,
            price_trend="flat", price_trend_pct=1.0,
        ))
        rec_both = evaluate(_signals(
            latest_batch_median=125.0, historical_median=100.0,
            price_trend="rising", price_trend_pct=18.0,
        ))
        assert rec_both.confidence > rec_one.confidence

    def test_skip_confidence_capped_at_075(self):
        """SKIP confidence never exceeds 0.75."""
        rec = evaluate(_signals(
            latest_batch_median=150.0, historical_median=100.0,
            price_trend="rising", price_trend_pct=30.0,
            poll_batch_count=10,
        ))
        assert rec.action == "skip"
        assert rec.confidence <= 0.75

    def test_no_skip_at_14pct_rise(self):
        """14% rising is below the 15% SKIP threshold."""
        rec = evaluate(_signals(
            latest_batch_median=105.0, historical_median=100.0,
            price_trend="rising", price_trend_pct=14.0,
        ))
        assert rec.action != "skip"

    def test_no_skip_at_19pct_overpriced(self):
        """19% above historical is below the 20% SKIP threshold."""
        rec = evaluate(_signals(
            latest_batch_median=119.0, historical_median=100.0,
            price_trend="flat",
        ))
        assert rec.action != "skip"


class TestDefaultWait:
    """Gate 4 — default WAIT when no strong signal fires."""

    def test_flat_market_returns_wait(self):
        rec = evaluate(_signals(
            latest_batch_median=100.0,
            historical_median=100.0,
            price_trend="flat",
            listing_trend="flat",
        ))
        assert rec.action == "wait"

    def test_wait_confidence_scales_with_maturity(self):
        rec_low = evaluate(_signals(poll_batch_count=2, history_span_days=2.0))
        rec_high = evaluate(_signals(poll_batch_count=4, history_span_days=8.0))
        assert rec_high.confidence > rec_low.confidence

    def test_wait_confidence_capped_at_060(self):
        rec = evaluate(_signals(
            poll_batch_count=10, history_span_days=14.0,
            price_trend="flat",
        ))
        assert rec.action == "wait"
        assert rec.confidence <= 0.60


class TestRecommendationMetadata:
    """Every recommendation carries version and signals snapshot."""

    def test_ruleset_version_present(self):
        rec = evaluate(_signals())
        assert rec.ruleset_version == RULESET_VERSION

    def test_signals_snapshot_preserved(self):
        sig = _signals(avg_price=123.45)
        rec = evaluate(sig)
        assert rec.signals_snapshot == sig.to_dict()

    def test_reasoning_is_nonempty_string(self):
        rec = evaluate(_signals())
        assert isinstance(rec.reasoning, str)
        assert len(rec.reasoning) > 0


class TestHistoryLabel:
    """_history_label returns human-friendly duration strings."""

    def test_less_than_one_day(self):
        assert _history_label(0.5) == "< 1 day"

    def test_exactly_one_day(self):
        assert _history_label(1.0) == "1 day"

    def test_rounds_down_to_one(self):
        assert _history_label(1.9) == "1 day"

    def test_multiple_days(self):
        assert _history_label(3.7) == "3 days"

    def test_two_weeks(self):
        assert _history_label(14.0) == "14 days"

    def test_zero(self):
        assert _history_label(0.0) == "< 1 day"


class TestReasoningIncludesHistory:
    """Gates 2-4 reasoning text includes actual history duration."""

    def test_buy_reasoning_includes_history(self):
        rec = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling", history_span_days=1.2,
        ))
        assert rec.action == "buy_now"
        assert "1 day" in rec.reasoning

    def test_skip_reasoning_includes_history(self):
        rec = evaluate(_signals(
            latest_batch_median=125.0, historical_median=100.0,
            price_trend="rising", price_trend_pct=18.0,
            history_span_days=3.5,
        ))
        assert rec.action == "skip"
        assert "3 days" in rec.reasoning

    def test_wait_reasoning_includes_history(self):
        rec = evaluate(_signals(
            latest_batch_median=100.0, historical_median=100.0,
            price_trend="flat", listing_trend="flat",
            history_span_days=7.0,
        ))
        assert rec.action == "wait"
        assert "7 days" in rec.reasoning

    def test_short_history_shows_less_than_one_day(self):
        rec = evaluate(_signals(
            latest_batch_median=100.0, historical_median=100.0,
            price_trend="flat", history_span_days=0.3,
        ))
        assert rec.action == "wait"
        assert "< 1 day" in rec.reasoning


# ===================================================================
# Category B: Idempotent Storage (with DB)
# ===================================================================


class TestRecordRecommendation:
    """Idempotent storage of deterministic recommendations."""

    def test_first_insert_returns_decision_id(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        result = record_recommendation(engine, item_id, "batch-001", rec)
        assert isinstance(result, int)
        assert result > 0

    def test_stored_event_type(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        dec_id = record_recommendation(engine, item_id, "batch-001", rec)
        with engine.connect() as conn:
            row = conn.execute(
                decisions.select().where(decisions.c.id == dec_id)
            ).fetchone()
            assert row._mapping["event_type"] == "deterministic_recommendation"

    def test_stored_fields_round_trip(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals(
            latest_batch_median=85.0, historical_median=100.0,
            price_trend="falling",
        ))
        dec_id = record_recommendation(engine, item_id, "batch-001", rec)
        with engine.connect() as conn:
            row = dict(conn.execute(
                decisions.select().where(decisions.c.id == dec_id)
            ).fetchone()._mapping)
        assert row["action"] == rec.action
        assert row["confidence"] == pytest.approx(rec.confidence)
        assert row["reasoning"] == rec.reasoning
        assert row["ruleset_version"] == RULESET_VERSION
        assert row["source_poll_batch_id"] == "batch-001"
        stored_signals = json.loads(row["computed_signals"])
        assert stored_signals["avg_price"] == pytest.approx(100.0)

    def test_duplicate_returns_none(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        first = record_recommendation(engine, item_id, "batch-001", rec)
        second = record_recommendation(engine, item_id, "batch-001", rec)
        assert first is not None
        assert second is None

    def test_duplicate_does_not_create_second_row(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-001", rec)
        record_recommendation(engine, item_id, "batch-001", rec)
        with engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM decisions WHERE "
                "event_type = 'deterministic_recommendation'"
            )).scalar()
        assert count == 1

    def test_different_batch_creates_new_row(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-001", rec)
        record_recommendation(engine, item_id, "batch-002", rec)
        with engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM decisions WHERE "
                "event_type = 'deterministic_recommendation'"
            )).scalar()
        assert count == 2

    def test_different_ruleset_creates_new_row(self, engine):
        """Future-proofing: different ruleset version = new recommendation."""
        item_id = _create_item(engine)
        rec_v1 = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-001", rec_v1)
        # Simulate a different version by modifying the rec
        rec_v2 = Recommendation(
            action=rec_v1.action,
            confidence=rec_v1.confidence,
            reasoning=rec_v1.reasoning,
            ruleset_version="v2.0-test",
            signals_snapshot=rec_v1.signals_snapshot,
        )
        result = record_recommendation(engine, item_id, "batch-001", rec_v2)
        assert result is not None


# ===================================================================
# Category C: Latest Recommendation Query (with DB)
# ===================================================================


class TestLatestRecommendation:
    """Dedicated query that cannot be hidden by other event types."""

    def test_returns_none_when_empty(self, engine):
        item_id = _create_item(engine)
        assert get_latest_deterministic_recommendation(engine, item_id) is None

    def test_returns_latest_by_timestamp(self, engine):
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-old", rec)
        record_recommendation(engine, item_id, "batch-new", rec)
        latest = get_latest_deterministic_recommendation(engine, item_id)
        assert latest is not None
        assert latest["source_poll_batch_id"] == "batch-new"

    def test_not_hidden_by_newer_price_drop_alert(self, engine):
        """A newer price_drop_alert must not hide the deterministic rec."""
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-001", rec)
        # Insert a newer price_drop_alert
        insert_decision(
            engine, item_id, "price_drop_alert",
            action=None, reasoning="Price dropped",
            timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        latest = get_latest_deterministic_recommendation(engine, item_id)
        assert latest is not None
        assert latest["event_type"] == "deterministic_recommendation"

    def test_not_hidden_by_newer_llm_reasoning(self, engine):
        """A newer llm_reasoning must not hide the deterministic rec."""
        item_id = _create_item(engine)
        rec = evaluate(_signals())
        record_recommendation(engine, item_id, "batch-001", rec)
        insert_decision(
            engine, item_id, "llm_reasoning",
            action="buy_now", confidence=0.8, reasoning="LLM says buy",
            timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        latest = get_latest_deterministic_recommendation(engine, item_id)
        assert latest is not None
        assert latest["event_type"] == "deterministic_recommendation"

    def test_returns_correct_item_only(self, engine):
        """With multiple items, returns only the requested item's rec."""
        id_a = _create_item(engine, "Item A")
        id_b = _create_item(engine, "Item B")
        rec_a = evaluate(_signals(latest_batch_median=85.0, historical_median=100.0,
                                  price_trend="falling"))
        rec_b = evaluate(_signals())
        record_recommendation(engine, id_a, "batch-a", rec_a)
        record_recommendation(engine, id_b, "batch-b", rec_b)
        latest_a = get_latest_deterministic_recommendation(engine, id_a)
        assert latest_a["action"] == "buy_now"
        latest_b = get_latest_deterministic_recommendation(engine, id_b)
        assert latest_b["action"] == "wait"


# ===================================================================
# Category D: Schema Migration
# ===================================================================


class TestSchemaMigration:
    """Additive migration adds new columns to decisions table."""

    def test_new_columns_exist(self, engine):
        inspector = inspect(engine)
        col_names = {c["name"] for c in inspector.get_columns("decisions")}
        assert "ruleset_version" in col_names
        assert "source_poll_batch_id" in col_names

    def test_migration_idempotent(self, engine):
        """Running create_all / migrate twice does not error."""
        from resale_price_agent.db import _migrate_schema
        _migrate_schema(engine)
        metadata.create_all(engine)
        inspector = inspect(engine)
        col_names = {c["name"] for c in inspector.get_columns("decisions")}
        assert "ruleset_version" in col_names

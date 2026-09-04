"""Deterministic recommendation engine — pure BUY / WAIT / SKIP rules.

Evaluates TrendSignals through a gated scoring pipeline with versioned
rules, evidence gates, and confidence scaling.  No LLM calls, no
external dependencies.

Storage is idempotent: the same (item, poll_batch, ruleset_version)
combination cannot produce duplicate recommendation rows.
"""

import json
import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from resale_price_agent.db import decisions, insert_decision
from resale_price_agent.signals import TrendSignals

log = logging.getLogger(__name__)

RULESET_VERSION = "v1.0"

# Gate 2 — BUY thresholds
BUY_MIN_DISCOUNT = 0.10        # 10% below historical median
BUY_DISCOUNT_TIER_2 = 0.15     # bonus confidence at 15%
BUY_DISCOUNT_TIER_3 = 0.20     # bonus confidence at 20%

# Gate 3 — SKIP thresholds
SKIP_OVERPRICED_RATIO = 1.20   # 20% above historical median
SKIP_RISING_PRICE_PCT = 15.0   # 15% rising price trend

# Gate 1 — staleness
STALE_HOURS = 72


def _history_label(span_days: float) -> str:
    """Human-friendly label for history_span_days."""
    days = int(span_days)
    if days < 1:
        return "< 1 day"
    if days == 1:
        return "1 day"
    return f"{days} days"


@dataclass(frozen=True)
class Recommendation:
    """Result of the deterministic rule engine."""

    action: str           # "buy_now" | "wait" | "skip"
    confidence: float     # 0.0–1.0
    reasoning: str        # human-readable explanation
    ruleset_version: str  # e.g. "v1.0"
    signals_snapshot: dict  # TrendSignals.to_dict() at decision time


def evaluate(signals: TrendSignals) -> Recommendation:
    """Pure function: TrendSignals in, Recommendation out.  No side effects."""
    snapshot = signals.to_dict()

    # Gate 0: insufficient data
    if not signals.sufficient_data:
        return Recommendation(
            action="wait",
            confidence=0.20,
            reasoning=(
                f"Insufficient history ({signals.snapshot_count} snapshots, "
                f"{signals.poll_batch_count} batch(es)). "
                f"Need more polling data."
            ),
            ruleset_version=RULESET_VERSION,
            signals_snapshot=snapshot,
        )

    # Null guard — defense in depth (Gate 0 should catch, but be explicit)
    if (
        signals.latest_batch_median is None
        or signals.historical_median is None
        or signals.freshness_hours is None
    ):
        return Recommendation(
            action="wait",
            confidence=0.20,
            reasoning="Missing required signal fields for evaluation.",
            ruleset_version=RULESET_VERSION,
            signals_snapshot=snapshot,
        )

    # Gate 1: stale data
    if signals.freshness_hours > STALE_HOURS:
        return Recommendation(
            action="wait",
            confidence=0.25,
            reasoning=(
                f"Data is stale ({signals.freshness_hours:.0f}h since last "
                f"poll). Signals may not reflect current market."
            ),
            ruleset_version=RULESET_VERSION,
            signals_snapshot=snapshot,
        )

    # Compute discount for Gates 2/3
    discount_pct = (
        (signals.historical_median - signals.latest_batch_median)
        / signals.historical_median
    )

    # Gate 2: BUY
    if discount_pct >= BUY_MIN_DISCOUNT and signals.price_trend != "rising":
        conf = 0.50
        if discount_pct >= BUY_DISCOUNT_TIER_2:
            conf += 0.10
        if discount_pct >= BUY_DISCOUNT_TIER_3:
            conf += 0.10
        if signals.price_trend == "falling":
            conf += 0.05
        if signals.listing_trend == "rising":
            conf += 0.05
        if signals.listing_trend == "falling":
            conf -= 0.05
        if signals.poll_batch_count >= 4:
            conf += 0.05
        if signals.history_span_days >= 7.0:
            conf += 0.05
        conf = min(conf, 0.90)

        history = _history_label(signals.history_span_days)
        return Recommendation(
            action="buy_now",
            confidence=conf,
            reasoning=(
                f"Median ${signals.latest_batch_median:.2f} is "
                f"{discount_pct:.0%} below historical "
                f"${signals.historical_median:.2f} "
                f"({signals.price_trend} prices, "
                f"{signals.listing_trend} supply). "
                f"Based on {history} of data."
            ),
            ruleset_version=RULESET_VERSION,
            signals_snapshot=snapshot,
        )

    # Gate 3: SKIP
    overpriced = (
        signals.latest_batch_median > signals.historical_median * SKIP_OVERPRICED_RATIO
    )
    strong_rise = (
        signals.price_trend == "rising"
        and (signals.price_trend_pct or 0) >= SKIP_RISING_PRICE_PCT
    )
    if overpriced or strong_rise:
        conf = 0.50
        if overpriced and strong_rise:
            conf += 0.10
        if signals.poll_batch_count >= 4:
            conf += 0.05
        conf = min(conf, 0.75)

        reasons = []
        if overpriced:
            over_pct = (
                (signals.latest_batch_median - signals.historical_median)
                / signals.historical_median
            )
            reasons.append(
                f"${signals.latest_batch_median:.2f} is {over_pct:.0%} above "
                f"historical ${signals.historical_median:.2f}"
            )
        if strong_rise:
            reasons.append(
                f"prices rising {signals.price_trend_pct:.0f}%"
            )
        history = _history_label(signals.history_span_days)
        return Recommendation(
            action="skip",
            confidence=conf,
            reasoning="; ".join(reasons) + f". Based on {history} of data.",
            ruleset_version=RULESET_VERSION,
            signals_snapshot=snapshot,
        )

    # Gate 4: default WAIT
    conf = 0.40
    if signals.price_trend == "flat":
        conf += 0.05
    if signals.poll_batch_count >= 3:
        conf += 0.05
    if signals.history_span_days >= 5.0:
        conf += 0.05
    conf = min(conf, 0.60)

    history = _history_label(signals.history_span_days)
    return Recommendation(
        action="wait",
        confidence=conf,
        reasoning=(
            f"No strong signal ({signals.price_trend} prices, "
            f"{signals.listing_trend} supply). "
            f"Based on {history} of data."
        ),
        ruleset_version=RULESET_VERSION,
        signals_snapshot=snapshot,
    )


def record_recommendation(
    engine,
    tracked_item_id: int,
    poll_batch_id: str,
    rec: Recommendation,
) -> int | None:
    """Store a deterministic recommendation idempotently.

    Returns the decision ID on success, or ``None`` if a recommendation
    for this (item, batch, ruleset_version) already exists.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(decisions.insert().values(
                tracked_item_id=tracked_item_id,
                event_type="deterministic_recommendation",
                timestamp=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                computed_signals=json.dumps(rec.signals_snapshot),
                action=rec.action,
                confidence=rec.confidence,
                reasoning=rec.reasoning,
                ruleset_version=rec.ruleset_version,
                source_poll_batch_id=poll_batch_id,
            ))
            return result.inserted_primary_key[0]
    except IntegrityError:
        log.debug(
            "Recommendation already recorded for item=%d batch=%s version=%s",
            tracked_item_id, poll_batch_id, rec.ruleset_version,
        )
        return None


def get_latest_deterministic_recommendation(
    engine, tracked_item_id: int,
) -> dict | None:
    """Return the most recent deterministic recommendation for an item.

    Filters to ``event_type='deterministic_recommendation'`` so newer
    price_drop_alert or llm_reasoning events cannot hide the recommendation.
    """
    stmt = (
        decisions.select()
        .where(decisions.c.tracked_item_id == tracked_item_id)
        .where(decisions.c.event_type == "deterministic_recommendation")
        .order_by(decisions.c.timestamp.desc())
        .limit(1)
    )
    with engine.connect() as conn:
        row = conn.execute(stmt).fetchone()
        return dict(row._mapping) if row else None

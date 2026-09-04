"""Longitudinal market-signal computation — pure Python/math."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
import statistics

from resale_price_agent.db import get_snapshots_for_item

MIN_SNAPSHOTS = 5
MIN_POLL_BATCHES = 2
WINDOW_DAYS = 14


@dataclass(frozen=True)
class TrendSignals:
    """Batch-aware summary of an item's recent market data."""

    sufficient_data: bool
    avg_price: float | None
    min_price: float | None
    max_price: float | None
    snapshot_count: int
    price_trend: str | None
    price_trend_pct: float | None
    listing_trend: str | None
    listing_trend_pct: float | None
    window_days: int

    # Defaults preserve existing callers that construct this class directly.
    poll_batch_count: int = 0
    history_span_days: float = 0.0
    latest_batch_time: str | None = None
    freshness_hours: float | None = None
    latest_batch_listing_count: int = 0
    latest_batch_median: float | None = None
    historical_median: float | None = None
    median_batch_price: float | None = None
    price_p25: float | None = None
    price_p75: float | None = None
    price_iqr: float | None = None
    unique_listing_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def compute_signals(
    engine,
    tracked_item_id: int,
    window_days: int = WINDOW_DAYS,
    min_snapshots: int = MIN_SNAPSHOTS,
    min_poll_batches: int = MIN_POLL_BATCHES,
) -> TrendSignals:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    snapshots = get_snapshots_for_item(engine, tracked_item_id, since=since)
    return _compute_signals_from_snapshots(
        snapshots, window_days=window_days,
        min_snapshots=min_snapshots, min_poll_batches=min_poll_batches,
    )


def compute_signals_by_condition(
    engine,
    tracked_item_id: int,
    window_days: int = WINDOW_DAYS,
    min_snapshots: int = MIN_SNAPSHOTS,
    min_poll_batches: int = MIN_POLL_BATCHES,
) -> dict[str, TrendSignals]:
    """Compute TrendSignals per condition tier plus an 'All' aggregate.

    Single DB fetch — partitions in-memory by normalized condition.
    """
    from resale_price_agent.conditions import normalize_condition

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    snapshots = get_snapshots_for_item(engine, tracked_item_id, since=since)

    # Partition by condition tier
    groups: dict[str, list[dict]] = {}
    for snap in snapshots:
        tier = normalize_condition(snap.get("condition"))
        groups.setdefault(tier, []).append(snap)

    result = {
        "All": _compute_signals_from_snapshots(
            snapshots, window_days=window_days,
            min_snapshots=min_snapshots, min_poll_batches=min_poll_batches,
        ),
    }
    for tier, tier_snapshots in groups.items():
        result[tier] = _compute_signals_from_snapshots(
            tier_snapshots, window_days=window_days,
            min_snapshots=min_snapshots, min_poll_batches=min_poll_batches,
        )

    return result


def _compute_signals_from_snapshots(
    snapshots: list[dict],
    window_days: int = WINDOW_DAYS,
    min_snapshots: int = MIN_SNAPSHOTS,
    min_poll_batches: int = MIN_POLL_BATCHES,
) -> TrendSignals:
    """Core signal computation from a pre-fetched list of snapshot dicts."""
    now = datetime.now(timezone.utc)

    if not snapshots:
        return TrendSignals(
            sufficient_data=False,
            avg_price=None,
            min_price=None,
            max_price=None,
            snapshot_count=0,
            price_trend=None,
            price_trend_pct=None,
            listing_trend=None,
            listing_trend_pct=None,
            window_days=window_days,
        )

    batches = _group_poll_batches(snapshots)
    batch_series = sorted(
        (
            (_latest_time(batch), batch_id, batch)
            for batch_id, batch in batches.items()
        ),
        key=lambda entry: entry[0],
    )
    poll_batch_count = len(batch_series)

    prices = [float(s["price"]) for s in snapshots]
    sorted_prices = sorted(prices)
    avg_price = round(sum(prices) / len(prices), 2)
    price_p25 = _percentile(sorted_prices, 0.25)
    price_p75 = _percentile(sorted_prices, 0.75)

    batch_medians = [
        statistics.median(float(s["price"]) for s in batch)
        for _, _, batch in batch_series
    ]
    latest_time, _, latest_batch = batch_series[-1]

    price_trend = None
    price_trend_pct = None
    listing_trend = None
    listing_trend_pct = None
    if poll_batch_count >= 2:
        midpoint = poll_batch_count // 2
        price_trend, price_trend_pct = _compare_periods(
            batch_medians[:midpoint], batch_medians[midpoint:],
        )

        unique_counts = [
            len({s["ebay_item_id"] for s in batch if s.get("ebay_item_id")})
            for _, _, batch in batch_series
        ]
        listing_trend, listing_trend_pct = _compare_periods(
            unique_counts[:midpoint], unique_counts[midpoint:],
        )

    first_time = batch_series[0][0]
    history_span_days = round(
        max(0.0, (latest_time - first_time).total_seconds()) / 86400,
        2,
    )
    freshness_hours = round(
        max(0.0, (now - latest_time).total_seconds()) / 3600,
        2,
    )

    return TrendSignals(
        sufficient_data=(
            len(snapshots) >= min_snapshots
            and poll_batch_count >= min_poll_batches
        ),
        avg_price=avg_price,
        min_price=min(prices),
        max_price=max(prices),
        snapshot_count=len(snapshots),
        price_trend=price_trend,
        price_trend_pct=price_trend_pct,
        listing_trend=listing_trend,
        listing_trend_pct=listing_trend_pct,
        window_days=window_days,
        poll_batch_count=poll_batch_count,
        history_span_days=history_span_days,
        latest_batch_time=latest_time.isoformat(),
        freshness_hours=freshness_hours,
        latest_batch_listing_count=len(
            {s["ebay_item_id"] for s in latest_batch if s.get("ebay_item_id")}
        ),
        latest_batch_median=round(batch_medians[-1], 2),
        historical_median=(
            round(statistics.median(batch_medians[:-1]), 2)
            if len(batch_medians) > 1 else None
        ),
        median_batch_price=round(statistics.median(batch_medians), 2),
        price_p25=price_p25,
        price_p75=price_p75,
        price_iqr=round(price_p75 - price_p25, 2),
        unique_listing_count=len(
            {s["ebay_item_id"] for s in snapshots if s.get("ebay_item_id")}
        ),
    )


def _group_poll_batches(snapshots: list[dict]) -> dict[str, list[dict]]:
    """Group rows by explicit batch ID, with a legacy timestamp fallback."""
    batches: dict[str, list[dict]] = {}
    for snapshot in snapshots:
        batch_id = snapshot.get("poll_batch_id")
        if not batch_id:
            batch_id = f"legacy:{snapshot.get('snapshot_time')}"
        batches.setdefault(str(batch_id), []).append(snapshot)
    return batches


def _as_utc(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_time(snapshots: list[dict]) -> datetime:
    return max(_as_utc(s["snapshot_time"]) for s in snapshots)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Return a linearly interpolated percentile for a non-empty sequence."""
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(sorted_values[lower], 2)
    weight = position - lower
    value = sorted_values[lower] + (
        sorted_values[upper] - sorted_values[lower]
    ) * weight
    return round(value, 2)


def _compare_periods(
    older_values: list[float], newer_values: list[float]
) -> tuple[str, float]:
    """Compare robust centers of older and newer poll-batch periods."""
    if not older_values or not newer_values:
        return ("flat", 0.0)

    older_median = statistics.median(older_values)
    newer_median = statistics.median(newer_values)
    if older_median == 0:
        return ("flat", 0.0)

    pct_change = round(
        ((newer_median - older_median) / older_median) * 100,
        2,
    )
    if abs(pct_change) < 2.0:
        return ("flat", pct_change)
    if pct_change > 0:
        return ("rising", pct_change)
    return ("falling", pct_change)

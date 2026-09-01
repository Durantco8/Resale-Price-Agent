"""Signal computation for the LLM decision layer — pure Python/math."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from resale_price_agent.db import get_snapshots_for_item

# Minimum snapshots required to compute meaningful signals.
MIN_SNAPSHOTS = 5

# Default lookback window.
WINDOW_DAYS = 14


@dataclass(frozen=True)
class TrendSignals:
    """LLM-ready summary of an item's recent price and supply trends."""

    sufficient_data: bool

    # Price stats over the window
    avg_price: float | None
    min_price: float | None
    max_price: float | None
    snapshot_count: int

    # Price trend: compare the average price of the recent half of the window
    # to the older half.
    price_trend: str | None        # "rising", "falling", or "flat"
    price_trend_pct: float | None  # signed percentage change (positive = rising)

    # Listing volume trend: same half-split comparison on listing counts.
    listing_trend: str | None      # "rising", "falling", or "flat"
    listing_trend_pct: float | None

    window_days: int

    def to_dict(self) -> dict:
        return asdict(self)


def compute_signals(
    engine,
    tracked_item_id: int,
    window_days: int = WINDOW_DAYS,
    min_snapshots: int = MIN_SNAPSHOTS,
) -> TrendSignals:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    snapshots = get_snapshots_for_item(engine, tracked_item_id, since=since)

    if len(snapshots) < min_snapshots:
        return TrendSignals(
            sufficient_data=False,
            avg_price=None,
            min_price=None,
            max_price=None,
            snapshot_count=len(snapshots),
            price_trend=None,
            price_trend_pct=None,
            listing_trend=None,
            listing_trend_pct=None,
            window_days=window_days,
        )

    prices = [s["price"] for s in snapshots]
    avg_price = round(sum(prices) / len(prices), 2)
    min_price = min(prices)
    max_price = max(prices)

    # --- Split into older vs newer halves by date ---
    # Snapshots are returned newest-first; reverse for chronological order.
    chronological = list(reversed(snapshots))
    midpoint = len(chronological) // 2
    older_half = chronological[:midpoint]
    newer_half = chronological[midpoint:]

    price_trend, price_trend_pct = _compare_halves(
        [s["price"] for s in older_half],
        [s["price"] for s in newer_half],
    )

    # --- Listing count trend ---
    # Group snapshots by date, then compare daily listing counts between
    # the two halves.
    older_daily = _daily_counts(older_half)
    newer_daily = _daily_counts(newer_half)
    listing_trend, listing_trend_pct = _compare_halves(
        list(older_daily.values()),
        list(newer_daily.values()),
    )

    return TrendSignals(
        sufficient_data=True,
        avg_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        snapshot_count=len(snapshots),
        price_trend=price_trend,
        price_trend_pct=price_trend_pct,
        listing_trend=listing_trend,
        listing_trend_pct=listing_trend_pct,
        window_days=window_days,
    )


def _daily_counts(snapshots: list[dict]) -> dict[str, int]:
    """Count listings per calendar date."""
    counts: dict[str, int] = defaultdict(int)
    for s in snapshots:
        ts = s["snapshot_time"]
        if isinstance(ts, datetime):
            day = ts.strftime("%Y-%m-%d")
        else:
            day = str(ts)[:10]
        counts[day] += 1
    return dict(counts)


def _compare_halves(
    older_values: list[float], newer_values: list[float]
) -> tuple[str, float]:
    """Compare average of older vs newer values. Returns (direction, pct_change)."""
    if not older_values or not newer_values:
        return ("flat", 0.0)

    older_avg = sum(older_values) / len(older_values)
    newer_avg = sum(newer_values) / len(newer_values)

    if older_avg == 0:
        return ("flat", 0.0)

    pct_change = round(((newer_avg - older_avg) / older_avg) * 100, 2)

    # Treat changes under 2% as flat to avoid noise.
    if abs(pct_change) < 2.0:
        return ("flat", pct_change)
    elif pct_change > 0:
        return ("rising", pct_change)
    else:
        return ("falling", pct_change)

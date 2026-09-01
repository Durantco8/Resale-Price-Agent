"""Storage layer — SQLAlchemy Core with SQLite/Postgres.

All public functions accept an explicit ``engine`` so callers (and tests)
can inject an in-memory SQLite database.  Transactions are explicit via
``engine.begin()``.
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)

metadata = MetaData()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

tracked_items = Table(
    "tracked_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("search_query", String, nullable=False),
    Column("normalized_query", String, nullable=False),
    Column("display_name", String, nullable=False),
    Column("is_seeded", Boolean, nullable=False, default=False),
    Column("status", String, nullable=False, default="collecting"),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("normalized_query", name="uq_tracked_items_normalized_query"),
)

snapshots = Table(
    "snapshots",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "tracked_item_id",
        Integer,
        ForeignKey("tracked_items.id"),
        nullable=False,
    ),
    Column("ebay_item_id", String, nullable=False),
    Column("title", String, nullable=False),
    Column("price", Float, nullable=False),
    Column("currency", String, nullable=False, default="USD"),
    Column("condition", String, nullable=True),
    Column("seller_feedback_score", Integer, nullable=True),
    Column("shipping_cost", Float, nullable=True),
    Column("item_location", String, nullable=True),
    Column("buying_format", String, nullable=True),
    Column("item_url", String, nullable=True),
    Column("snapshot_time", DateTime, nullable=False),
)

decisions = Table(
    "decisions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "tracked_item_id",
        Integer,
        ForeignKey("tracked_items.id"),
        nullable=False,
    ),
    Column("timestamp", DateTime, nullable=False),
    Column("event_type", String, nullable=False),
    Column("computed_signals", Text, nullable=True),
    Column("action", String, nullable=True),
    Column("confidence", Float, nullable=True),
    Column("reasoning", Text, nullable=True),
    Column("outcome", Text, nullable=True),
)

alerts = Table(
    "alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String, nullable=False),
    Column(
        "tracked_item_id",
        Integer,
        ForeignKey("tracked_items.id"),
        nullable=False,
    ),
    Column("condition", String, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("unsubscribe_token", String, nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False),
)

# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

def get_engine(db_url: str = "sqlite:///resale_agent.db"):
    engine = create_engine(db_url, echo=False)
    metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Query normalization + dedupe
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(raw: str) -> str:
    """Lowercase, collapse whitespace, strip.

    >>> normalize_query("  Jordan  4   Retro  ")
    'jordan 4 retro'
    """
    return _WHITESPACE_RE.sub(" ", raw.strip()).lower()


def get_or_create_tracked_item(
    engine, raw_query: str,
) -> tuple[dict, bool]:
    """Find or create a tracked_item for *raw_query*.

    Returns ``(row_dict, created)`` where *created* is True if a new row
    was inserted.  Deduplication is based on ``normalized_query``.
    """
    norm = normalize_query(raw_query)
    if not norm:
        raise ValueError("Search query must not be empty")

    # Check for existing match first
    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(
                tracked_items.c.normalized_query == norm
            )
        ).fetchone()
        if row:
            return dict(row._mapping), False

    # Insert new row
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.insert().values(
                search_query=raw_query.strip(),
                normalized_query=norm,
                display_name=raw_query.strip(),
                is_seeded=False,
                status="collecting",
                created_at=datetime.now(timezone.utc),
            )
        )
        item_id = result.inserted_primary_key[0]

    # Return the full row
    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(tracked_items.c.id == item_id)
        ).fetchone()
        return dict(row._mapping), True


def seed_tracked_item(
    engine, raw_query: str, display_name: str | None = None,
) -> tuple[dict, bool]:
    """Create or retrieve a seeded tracked item.

    Like ``get_or_create_tracked_item`` but sets ``is_seeded=True``.
    If the item already exists, updates ``is_seeded`` to True (a seeded
    item that was previously user-created gets promoted).

    Returns ``(row_dict, created)``.
    """
    norm = normalize_query(raw_query)
    if not norm:
        raise ValueError("Search query must not be empty")

    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(
                tracked_items.c.normalized_query == norm
            )
        ).fetchone()

    if row:
        row_dict = dict(row._mapping)
        if not row_dict["is_seeded"]:
            with engine.begin() as conn:
                conn.execute(
                    tracked_items.update()
                    .where(tracked_items.c.id == row_dict["id"])
                    .values(is_seeded=True)
                )
            row_dict["is_seeded"] = True
        return row_dict, False

    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.insert().values(
                search_query=raw_query.strip(),
                normalized_query=norm,
                display_name=(display_name or raw_query).strip(),
                is_seeded=True,
                status="collecting",
                created_at=datetime.now(timezone.utc),
            )
        )
        item_id = result.inserted_primary_key[0]

    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(tracked_items.c.id == item_id)
        ).fetchone()
        return dict(row._mapping), True


# ---------------------------------------------------------------------------
# Tracked items — read helpers
# ---------------------------------------------------------------------------

def get_tracked_item(engine, item_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(tracked_items.c.id == item_id)
        ).fetchone()
        return dict(row._mapping) if row else None


def get_tracked_item_by_query(engine, raw_query: str) -> dict | None:
    norm = normalize_query(raw_query)
    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(
                tracked_items.c.normalized_query == norm
            )
        ).fetchone()
        return dict(row._mapping) if row else None


def get_all_tracked_items(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(tracked_items.select()).fetchall()
        return [dict(r._mapping) for r in rows]


def get_seeded_items(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            tracked_items.select().where(tracked_items.c.is_seeded == True)  # noqa: E712
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def set_tracked_item_status(engine, item_id: int, status: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.update()
            .where(tracked_items.c.id == item_id)
            .values(status=status)
        )
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

def insert_snapshots(engine, tracked_item_id: int, snapshot_list: list[dict]) -> int:
    if not snapshot_list:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        {
            "tracked_item_id": tracked_item_id,
            "ebay_item_id": s["ebay_item_id"],
            "title": s["title"],
            "price": s["price"],
            "currency": s.get("currency", "USD"),
            "condition": s.get("condition"),
            "seller_feedback_score": s.get("seller_feedback_score"),
            "shipping_cost": s.get("shipping_cost"),
            "item_location": s.get("item_location"),
            "buying_format": s.get("buying_format"),
            "item_url": s.get("item_url"),
            "snapshot_time": s.get("snapshot_time", now),
        }
        for s in snapshot_list
    ]
    with engine.begin() as conn:
        conn.execute(snapshots.insert(), rows)
    return len(rows)


def get_snapshots_for_item(
    engine, tracked_item_id: int, limit: int | None = None,
    since: datetime | None = None,
) -> list[dict]:
    stmt = (
        snapshots.select()
        .where(snapshots.c.tracked_item_id == tracked_item_id)
        .order_by(snapshots.c.snapshot_time.desc())
    )
    if since is not None:
        stmt = stmt.where(snapshots.c.snapshot_time >= since)
    if limit is not None:
        stmt = stmt.limit(limit)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def insert_decision(engine, tracked_item_id: int, event_type: str, **kwargs) -> int:
    values = {
        "tracked_item_id": tracked_item_id,
        "timestamp": kwargs.get("timestamp", datetime.now(timezone.utc)),
        "event_type": event_type,
        "computed_signals": kwargs.get("computed_signals"),
        "action": kwargs.get("action"),
        "confidence": kwargs.get("confidence"),
        "reasoning": kwargs.get("reasoning"),
        "outcome": kwargs.get("outcome"),
    }
    with engine.begin() as conn:
        result = conn.execute(decisions.insert().values(**values))
        return result.inserted_primary_key[0]


def get_decisions_for_item(
    engine, tracked_item_id: int, limit: int | None = None,
) -> list[dict]:
    stmt = (
        decisions.select()
        .where(decisions.c.tracked_item_id == tracked_item_id)
        .order_by(decisions.c.timestamp.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        return [dict(r._mapping) for r in rows]


def get_recent_alerts_decisions(
    engine, tracked_item_id: int, since: datetime | None = None,
) -> list[dict]:
    """Return price_drop_alert decisions for a tracked item since *since*."""
    stmt = (
        decisions.select()
        .where(decisions.c.tracked_item_id == tracked_item_id)
        .where(decisions.c.event_type == "price_drop_alert")
    )
    if since is not None:
        stmt = stmt.where(decisions.c.timestamp >= since)
    stmt = stmt.order_by(decisions.c.timestamp.desc())
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
        return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Alerts (email subscriptions)
# ---------------------------------------------------------------------------

def create_alert(
    engine, email: str, tracked_item_id: int, condition: str,
) -> dict:
    """Create a new alert subscription. Returns the full row dict."""
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        result = conn.execute(
            alerts.insert().values(
                email=email,
                tracked_item_id=tracked_item_id,
                condition=condition,
                active=True,
                unsubscribe_token=token,
                created_at=now,
            )
        )
        alert_id = result.inserted_primary_key[0]

    with engine.connect() as conn:
        row = conn.execute(
            alerts.select().where(alerts.c.id == alert_id)
        ).fetchone()
        return dict(row._mapping)


def get_active_alerts_for_item(engine, tracked_item_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            alerts.select()
            .where(alerts.c.tracked_item_id == tracked_item_id)
            .where(alerts.c.active == True)  # noqa: E712
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def unsubscribe_by_token(engine, token: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            alerts.update()
            .where(alerts.c.unsubscribe_token == token)
            .values(active=False)
        )
        return result.rowcount > 0

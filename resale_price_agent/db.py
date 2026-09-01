"""Storage layer — SQLAlchemy Core with SQLite.

All public functions accept an explicit ``engine`` so callers (and tests)
can inject an in-memory SQLite database.
"""

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
    Column("target_price", Float, nullable=True),
    Column("active", Boolean, nullable=False, default=True),
    Column("date_added", DateTime, nullable=False),
)

listing_snapshots = Table(
    "listing_snapshots",
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
    Column("event_type", String, nullable=False),  # price_drop_alert | llm_reasoning
    Column("computed_signals", Text, nullable=True),  # JSON string
    Column("action", String, nullable=True),  # buy_now | wait | skip
    Column("confidence", Float, nullable=True),
    Column("reasoning", Text, nullable=True),
    Column("outcome", Text, nullable=True),  # filled in later for backtesting
)


# ---------------------------------------------------------------------------
# Engine helper
# ---------------------------------------------------------------------------

def get_engine(db_path: str = "resale_agent.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Tracked items
# ---------------------------------------------------------------------------

def add_tracked_item(engine, search_query: str, target_price: float | None = None) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.insert().values(
                search_query=search_query,
                target_price=target_price,
                active=True,
                date_added=datetime.now(timezone.utc),
            )
        )
        return result.inserted_primary_key[0]


def get_tracked_item(engine, item_id: int) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            tracked_items.select().where(tracked_items.c.id == item_id)
        ).fetchone()
        return dict(row._mapping) if row else None


def get_all_tracked_items(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(tracked_items.select()).fetchall()
        return [dict(r._mapping) for r in rows]


def get_active_tracked_items(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            tracked_items.select().where(tracked_items.c.active == True)  # noqa: E712
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def set_tracked_item_active(engine, item_id: int, active: bool) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.update()
            .where(tracked_items.c.id == item_id)
            .values(active=active)
        )
        return result.rowcount > 0


def remove_tracked_item(engine, item_id: int) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.delete().where(tracked_items.c.id == item_id)
        )
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# Listing snapshots
# ---------------------------------------------------------------------------

def insert_snapshots(engine, tracked_item_id: int, snapshots: list[dict]) -> int:
    if not snapshots:
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
        for s in snapshots
    ]
    with engine.begin() as conn:
        conn.execute(listing_snapshots.insert(), rows)
    return len(rows)


def get_snapshots_for_item(
    engine, tracked_item_id: int, limit: int | None = None
) -> list[dict]:
    stmt = (
        listing_snapshots.select()
        .where(listing_snapshots.c.tracked_item_id == tracked_item_id)
        .order_by(listing_snapshots.c.snapshot_time.desc())
    )
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
    engine, tracked_item_id: int, limit: int | None = None
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


def update_decision_outcome(engine, decision_id: int, outcome: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            decisions.update()
            .where(decisions.c.id == decision_id)
            .values(outcome=outcome)
        )
        return result.rowcount > 0

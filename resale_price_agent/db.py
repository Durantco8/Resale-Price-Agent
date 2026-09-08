"""Storage layer — SQLAlchemy Core with SQLite/Postgres.

All public functions accept an explicit ``engine`` so callers (and tests)
can inject an in-memory SQLite database.  Transactions are explicit via
``engine.begin()``.
"""

import os
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    inspect,
    or_,
    text,
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
    Column("owner", String, nullable=True, default=None),
    Column("ebay_category_id", String, nullable=True, default=None),
    Column("category", String, nullable=True, default=None),
    Column("image_url", String, nullable=True, default=None),
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
    # One UUID per item poll.  Nullable at the physical-schema level so the
    # existing SQLite database can receive this additive column without a
    # table rewrite; all application inserts populate it, and the migration
    # backfills every legacy row.
    Column("poll_batch_id", String, nullable=True),
    Column("image_url", String, nullable=True),
)

Index(
    "ix_snapshots_tracked_item_poll_batch",
    snapshots.c.tracked_item_id,
    snapshots.c.poll_batch_id,
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
    Column("ruleset_version", String, nullable=True),
    Column("source_poll_batch_id", String, nullable=True),
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

def _resolve_db_url(db_url: str | None = None) -> str:
    """Resolve DB URL: explicit arg > DATABASE_URL env var > SQLite default."""
    if db_url:
        return db_url
    url = os.environ.get("DATABASE_URL", "sqlite:///resale_agent.db")
    # Render uses postgres:// but SQLAlchemy requires postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def get_engine(db_url: str | None = None):
    engine = create_engine(_resolve_db_url(db_url), echo=False)
    _migrate_schema(engine)
    metadata.create_all(engine)
    return engine


def _extract_listing_url(ebay_item_id: str) -> str:
    """Build an eBay /itm/ URL from a stored item ID like ``v1|123456|0``."""
    parts = ebay_item_id.split("|")
    listing_id = parts[1] if len(parts) >= 2 else ebay_item_id
    return f"https://www.ebay.com/itm/{listing_id}"


def _legacy_poll_batch_id(tracked_item_id: int, snapshot_time) -> str:
    """Build a stable batch ID for legacy rows sharing item + timestamp."""
    identity = f"resale-price-agent:{tracked_item_id}:{snapshot_time}"
    return uuid.uuid5(uuid.NAMESPACE_URL, identity).hex


def _migrate_schema(engine) -> None:
    """Apply small, additive schema migrations before ``create_all``.

    Existing snapshots were inserted with one identical ``snapshot_time`` per
    item poll, so item + timestamp is a safe legacy grouping for the one-time
    poll-batch backfill.  New writes always receive an explicit UUID.
    """
    inspector = inspect(engine)
    if "snapshots" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("snapshots")}
    with engine.begin() as conn:
        if "poll_batch_id" not in column_names:
            conn.execute(text("ALTER TABLE snapshots ADD COLUMN poll_batch_id VARCHAR"))

        legacy_rows = conn.execute(
            text(
                "SELECT id, tracked_item_id, snapshot_time "
                "FROM snapshots WHERE poll_batch_id IS NULL OR poll_batch_id = ''"
            )
        ).mappings().all()
        if legacy_rows:
            conn.execute(
                text(
                    "UPDATE snapshots SET poll_batch_id = :poll_batch_id "
                    "WHERE id = :snapshot_id"
                ),
                [
                    {
                        "snapshot_id": row["id"],
                        "poll_batch_id": _legacy_poll_batch_id(
                            row["tracked_item_id"], row["snapshot_time"]
                        ),
                    }
                    for row in legacy_rows
                ],
            )

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_snapshots_tracked_item_poll_batch "
                "ON snapshots (tracked_item_id, poll_batch_id)"
            )
        )

    # --- decisions table: deterministic recommendation provenance ---
    if "decisions" in inspector.get_table_names():
        dec_cols = {c["name"] for c in inspector.get_columns("decisions")}
        with engine.begin() as conn:
            if "ruleset_version" not in dec_cols:
                conn.execute(text(
                    "ALTER TABLE decisions ADD COLUMN ruleset_version VARCHAR"
                ))
            if "source_poll_batch_id" not in dec_cols:
                conn.execute(text(
                    "ALTER TABLE decisions ADD COLUMN source_poll_batch_id VARCHAR"
                ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_deterministic_rec "
                "ON decisions (tracked_item_id, source_poll_batch_id, "
                "ruleset_version) "
                "WHERE event_type = 'deterministic_recommendation'"
            ))

    # --- Fix snapshot URLs: rewrite /p/ product pages to /itm/ listing URLs ---
    if "snapshots" in inspector.get_table_names():
        snap_cols = {c["name"] for c in inspector.get_columns("snapshots")}
        if "ebay_item_id" in snap_cols and "item_url" in snap_cols:
            with engine.begin() as conn:
                # ebay_item_id is stored as "v1|123456|0"; extract the middle
                # segment for the /itm/ URL.  Works on both SQLite and Postgres.
                bad_rows = conn.execute(
                    text(
                        "SELECT id, ebay_item_id FROM snapshots "
                        "WHERE item_url LIKE '%/p/%' "
                        "AND ebay_item_id IS NOT NULL AND ebay_item_id != ''"
                    )
                ).mappings().all()
                if bad_rows:
                    conn.execute(
                        text(
                            "UPDATE snapshots SET item_url = :url WHERE id = :sid"
                        ),
                        [
                            {
                                "sid": row["id"],
                                "url": _extract_listing_url(row["ebay_item_id"]),
                            }
                            for row in bad_rows
                        ],
                    )


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
    engine, raw_query: str, owner: str | None = None,
) -> tuple[dict, bool, bool]:
    """Find or create a tracked_item for *raw_query*.

    Returns ``(row_dict, created, claimed)`` where *created* is True if a
    new row was inserted, and *claimed* is True if an existing unowned
    item had its ``owner`` field set by this call.
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
            row_dict = dict(row._mapping)
            claimed = False
            if owner and row_dict.get("owner") is None:
                with engine.begin() as conn2:
                    conn2.execute(
                        tracked_items.update()
                        .where(tracked_items.c.id == row_dict["id"])
                        .values(owner=owner)
                    )
                row_dict["owner"] = owner
                claimed = True
            return row_dict, False, claimed

    # Insert new row
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.insert().values(
                search_query=raw_query.strip(),
                normalized_query=norm,
                display_name=raw_query.strip(),
                is_seeded=False,
                owner=owner,
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
        return dict(row._mapping), True, False


def seed_tracked_item(
    engine, raw_query: str, display_name: str | None = None,
    ebay_category_id: str | None = None,
    category: str | None = None,
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
        updates = {}
        if not row_dict["is_seeded"]:
            updates["is_seeded"] = True
        if ebay_category_id and row_dict.get("ebay_category_id") != ebay_category_id:
            updates["ebay_category_id"] = ebay_category_id
        if category and row_dict.get("category") != category:
            updates["category"] = category
        if updates:
            with engine.begin() as conn:
                conn.execute(
                    tracked_items.update()
                    .where(tracked_items.c.id == row_dict["id"])
                    .values(**updates)
                )
            row_dict.update(updates)
        return row_dict, False

    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.insert().values(
                search_query=raw_query.strip(),
                normalized_query=norm,
                display_name=(display_name or raw_query).strip(),
                is_seeded=True,
                ebay_category_id=ebay_category_id,
                category=category,
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


def suggest_tracked_items(engine, query: str, limit: int = 8) -> list[dict]:
    """Return tracked items whose display_name contains *query* (case-insensitive)."""
    pattern = f"%{query}%"
    with engine.connect() as conn:
        rows = conn.execute(
            tracked_items.select()
            .where(
                or_(
                    func.lower(tracked_items.c.display_name).contains(query.lower()),
                    func.lower(tracked_items.c.search_query).contains(query.lower()),
                )
            )
            .order_by(tracked_items.c.display_name)
            .limit(limit)
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def backfill_snapshot_images(engine, item_id: int, image_map: dict) -> int:
    """Update image_url on snapshots that have NULL image_url.

    *image_map* maps ebay_item_id → image_url.
    Returns number of rows updated.
    """
    if not image_map:
        return 0
    updated = 0
    with engine.begin() as conn:
        for ebay_id, url in image_map.items():
            if not url:
                continue
            result = conn.execute(
                snapshots.update()
                .where(snapshots.c.tracked_item_id == item_id)
                .where(snapshots.c.ebay_item_id == ebay_id)
                .where(snapshots.c.image_url.is_(None))
                .values(image_url=url)
            )
            updated += result.rowcount
    return updated


def update_tracked_item_image(engine, item_id: int, image_url: str) -> bool:
    """Set image_url on a tracked item if it's currently NULL."""
    with engine.begin() as conn:
        result = conn.execute(
            tracked_items.update()
            .where(tracked_items.c.id == item_id)
            .where(tracked_items.c.image_url.is_(None))
            .values(image_url=image_url)
        )
        return result.rowcount > 0


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

def insert_snapshots(
    engine,
    tracked_item_id: int,
    snapshot_list: list[dict],
    poll_batch_id: str | None = None,
) -> int:
    if not snapshot_list:
        return 0
    now = datetime.now(timezone.utc)
    batch_id = poll_batch_id or uuid.uuid4().hex
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
            "poll_batch_id": batch_id,
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


def get_seen_ebay_ids(engine, tracked_item_id: int) -> set[str]:
    """Return the set of ebay_item_ids already stored for a tracked item."""
    from sqlalchemy import select
    stmt = (
        select(snapshots.c.ebay_item_id)
        .where(snapshots.c.tracked_item_id == tracked_item_id)
        .distinct()
    )
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(stmt)}


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

"""Flask application factory.

The web service exposes search, alert, and item detail endpoints.
Polling and seeding are handled by a separate background worker process
and are deliberately NOT wired into any route here.

Uses the app factory pattern so tests can inject an in-memory SQLite
engine and run without any real API calls.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from resale_price_agent.db import (
    create_alert,
    get_decisions_for_item,
    get_engine,
    get_seeded_items,
    get_snapshots_for_item,
    get_tracked_item,
    metadata,
    normalize_query,
    suggest_tracked_items,
    unsubscribe_by_token,
)
from resale_price_agent.conditions import label_listings
from resale_price_agent.signals import compute_signals, compute_signals_by_condition


def create_app(config=None):
    app = Flask(__name__)

    # --- Configuration ---
    app.config.update(config or {})

    # --- DB engine ---
    engine = app.config.get("ENGINE")
    if engine is None:
        engine = get_engine()
        app.config["ENGINE"] = engine

    # --- CORS ---
    CORS(app)

    # --- Rate limiter ---
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )

    search_limit = app.config.get("SEARCH_RATE_LIMIT", "30/minute")
    alert_limit = app.config.get("ALERT_RATE_LIMIT", "10/minute")

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/api/suggest")
    def api_suggest():
        q = request.args.get("q", "").strip()
        if not q or len(q) < 2:
            return jsonify([])
        items = suggest_tracked_items(engine, q)
        return jsonify([
            {
                "id": item["id"],
                "display_name": item["display_name"],
                "image_url": item.get("image_url"),
                "status": item["status"],
            }
            for item in items
        ])

    @app.route("/api/search")
    @limiter.limit(search_limit)
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"error": "Missing or empty 'q' parameter."}), 400

        # Search only returns existing tracked items — no auto-creation
        items = suggest_tracked_items(engine, q, limit=1)
        if not items:
            return jsonify({"error": "No tracked items match your search. Try browsing trending items or request a card to be tracked."}), 404

        item = items[0]
        item_id = item["id"]
        item_snapshots = get_snapshots_for_item(engine, item_id)
        item_decisions = get_decisions_for_item(engine, item_id)

        return jsonify({
            "tracked_item": _serialize_item(item),
            "created": False,
            "status": item["status"],
            "snapshot_count": len(item_snapshots),
            "snapshots": [_serialize_row(s) for s in item_snapshots],
            "decisions": [_serialize_row(d) for d in item_decisions],
        })

    @app.route("/api/alerts", methods=["POST"])
    @limiter.limit(alert_limit)
    def api_create_alert():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON."}), 400

        email = (data.get("email") or "").strip()
        tracked_item_id = data.get("tracked_item_id")
        condition = (data.get("condition") or "").strip()

        errors = []
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if tracked_item_id is None:
            errors.append("tracked_item_id is required.")
        if not condition:
            errors.append("condition is required (e.g. 'price_below:180.00' or 'buy_now').")
        if errors:
            return jsonify({"error": " ".join(errors)}), 400

        item = get_tracked_item(engine, int(tracked_item_id))
        if item is None:
            return jsonify({"error": "Tracked item not found."}), 404

        alert = create_alert(engine, email, item["id"], condition)

        # Return confirmation without exposing the unsubscribe token —
        # that's only delivered via email.
        return jsonify({
            "id": alert["id"],
            "email": alert["email"],
            "tracked_item_id": alert["tracked_item_id"],
            "condition": alert["condition"],
            "active": alert["active"],
        }), 201

    @app.route("/api/unsubscribe/<token>")
    def api_unsubscribe(token):
        success = unsubscribe_by_token(engine, token)
        if success:
            return jsonify({"message": "You have been unsubscribed."})
        return jsonify({"error": "Invalid or expired unsubscribe link."}), 404

    @app.route("/api/trending")
    def api_trending():
        items = get_seeded_items(engine)
        results = []
        for item in items:
            snap_count = len(get_snapshots_for_item(engine, item["id"]))
            signals = compute_signals(engine, item["id"])
            signals_summary = None
            if signals.sufficient_data:
                signals_summary = {
                    "latest_batch_median": signals.latest_batch_median,
                    "price_trend": signals.price_trend,
                    "price_trend_pct": signals.price_trend_pct,
                    "history_span_days": signals.history_span_days,
                }
            results.append({
                "tracked_item": _serialize_item(item),
                "snapshot_count": snap_count,
                "status": item["status"],
                "signals_summary": signals_summary,
            })
        # Richest data first
        results.sort(key=lambda r: r["snapshot_count"], reverse=True)
        return jsonify(results)

    @app.route("/api/items/<int:item_id>")
    def api_item_detail(item_id):
        item = get_tracked_item(engine, item_id)
        if item is None:
            return jsonify({"error": "Item not found."}), 404

        item_snapshots = get_snapshots_for_item(engine, item_id)
        item_decisions = get_decisions_for_item(engine, item_id)
        signals_by_cond = compute_signals_by_condition(engine, item_id)
        listing_labels = label_listings(item_snapshots, signals_by_cond)

        return jsonify({
            "tracked_item": _serialize_item(item),
            "status": item["status"],
            "snapshot_count": len(item_snapshots),
            "snapshots": [_serialize_row(s) for s in item_snapshots],
            "decisions": [_serialize_row(d) for d in item_decisions],
            "signals": signals_by_cond["All"].to_dict(),
            "signals_by_condition": {
                k: v.to_dict() for k, v in signals_by_cond.items()
            },
            "listing_labels": listing_labels,
        })

    return app


# ---------------------------------------------------------------------------
# Serialization helpers (datetime → ISO string for JSON)
# ---------------------------------------------------------------------------

def _serialize_row(row: dict) -> dict:
    """Convert a DB row dict to JSON-safe types."""
    from datetime import datetime
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            # All DB timestamps are UTC; append Z so JS converts to local time
            iso = v.isoformat()
            out[k] = iso + "Z" if not v.utcoffset() else iso
        else:
            out[k] = v
    return out


_serialize_item = _serialize_row

"""Flask application factory.

The web service exposes search, alert, and item detail endpoints.
Polling and seeding are handled by a separate background worker process
and are deliberately NOT wired into any route here.

Uses the app factory pattern so tests can inject an in-memory SQLite
engine and run without any real API calls.
"""

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine

from resale_price_agent.db import (
    create_alert,
    get_decisions_for_item,
    get_seeded_items,
    get_snapshots_for_item,
    get_tracked_item,
    metadata,
    unsubscribe_by_token,
)
from resale_price_agent.recommendation import get_latest_deterministic_recommendation
from resale_price_agent.search import search


def create_app(config=None):
    app = Flask(__name__)

    # --- Configuration ---
    app.config.update(config or {})

    # --- DB engine ---
    engine = app.config.get("ENGINE")
    if engine is None:
        db_url = app.config.get("DATABASE_URL", "sqlite:///resale_agent.db")
        engine = create_engine(db_url, echo=False)
        metadata.create_all(engine)
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

    @app.route("/api/search")
    @limiter.limit(search_limit)
    def api_search():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"error": "Missing or empty 'q' parameter."}), 400

        try:
            result = search(engine, q)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({
            "tracked_item": _serialize_item(result["tracked_item"]),
            "created": result["created"],
            "status": result["status"],
            "snapshot_count": result["snapshot_count"],
            "snapshots": [_serialize_row(s) for s in result["snapshots"]],
            "decisions": [_serialize_row(d) for d in result["decisions"]],
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
            latest_decision = None
            decs = get_decisions_for_item(engine, item["id"], limit=1)
            if decs:
                latest_decision = _serialize_row(decs[0])
            rec = get_latest_deterministic_recommendation(engine, item["id"])
            results.append({
                "tracked_item": _serialize_item(item),
                "snapshot_count": snap_count,
                "status": item["status"],
                "latest_decision": latest_decision,
                "recommendation": _serialize_row(rec) if rec else None,
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
        rec = get_latest_deterministic_recommendation(engine, item_id)

        return jsonify({
            "tracked_item": _serialize_item(item),
            "status": item["status"],
            "snapshot_count": len(item_snapshots),
            "snapshots": [_serialize_row(s) for s in item_snapshots],
            "decisions": [_serialize_row(d) for d in item_decisions],
            "recommendation": _serialize_row(rec) if rec else None,
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
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


_serialize_item = _serialize_row

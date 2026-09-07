"""Tests for the Flask API layer — all using test client, no real network."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from resale_price_agent.app import create_app
from resale_price_agent.db import (
    create_alert,
    get_or_create_tracked_item,
    insert_decision,
    insert_snapshots,
    metadata,
)
from resale_price_agent.signals import compute_signals


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    metadata.create_all(eng)
    return eng


@pytest.fixture
def client(engine):
    app = create_app(config={
        "ENGINE": engine,
        "TESTING": True,
        # High limits so normal tests don't hit them
        "SEARCH_RATE_LIMIT": "100/minute",
        "ALERT_RATE_LIMIT": "100/minute",
    })
    with app.test_client() as c:
        yield c


@pytest.fixture
def rate_limited_client(engine):
    app = create_app(config={
        "ENGINE": engine,
        "TESTING": True,
        "SEARCH_RATE_LIMIT": "3/minute",
        "ALERT_RATE_LIMIT": "2/minute",
    })
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_untracked_item_returns_404(self, client, engine):
        resp = client.get("/api/search?q=Jordan 4 Retro")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_existing_search(self, client, engine):
        get_or_create_tracked_item(engine, "Jordan 4 Retro")

        resp = client.get("/api/search?q=Jordan 4 Retro")
        data = resp.get_json()

        assert resp.status_code == 200
        assert data["created"] is False

    def test_returns_snapshots_and_decisions(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        insert_snapshots(engine, item["id"], [
            {"ebay_item_id": "v1|111|0", "title": "J4", "price": 200.0},
        ])
        insert_decision(engine, item["id"], "llm_reasoning", action="wait")

        resp = client.get("/api/search?q=Jordan 4 Retro")
        data = resp.get_json()

        assert data["snapshot_count"] == 1
        assert len(data["snapshots"]) == 1
        assert len(data["decisions"]) == 1

    def test_empty_query_400(self, client):
        resp = client.get("/api/search?q=")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_missing_query_400(self, client):
        resp = client.get("/api/search")
        assert resp.status_code == 400


class TestSuggest:
    def test_returns_matching_items(self, client, engine):
        get_or_create_tracked_item(engine, "Charizard Base Set Holo")
        get_or_create_tracked_item(engine, "Charizard VMAX")
        get_or_create_tracked_item(engine, "Pikachu Base Set")

        resp = client.get("/api/suggest?q=Charizard")
        data = resp.get_json()

        assert resp.status_code == 200
        assert len(data) == 2
        names = [item["display_name"] for item in data]
        assert "Charizard Base Set Holo" in names
        assert "Charizard VMAX" in names

    def test_short_query_returns_empty(self, client):
        resp = client.get("/api/suggest?q=C")
        assert resp.get_json() == []

    def test_no_matches_returns_empty(self, client, engine):
        get_or_create_tracked_item(engine, "Charizard Base Set")
        resp = client.get("/api/suggest?q=Pikachu")
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# POST /api/alerts
# ---------------------------------------------------------------------------

class TestCreateAlert:
    def test_create_price_alert(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "user@example.com",
            "tracked_item_id": item["id"],
            "condition": "price_below:180.00",
        })

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["email"] == "user@example.com"
        assert data["condition"] == "price_below:180.00"
        assert data["active"] is True
        assert "id" in data

    def test_create_buy_now_alert(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "user@example.com",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })

        assert resp.status_code == 201

    def test_token_not_in_response(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "user@example.com",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })

        data = resp.get_json()
        assert "unsubscribe_token" not in data

    def test_missing_email_400(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })
        assert resp.status_code == 400

    def test_invalid_email_400(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "not-an-email",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })
        assert resp.status_code == 400

    def test_missing_condition_400(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "a@b.com",
            "tracked_item_id": item["id"],
        })
        assert resp.status_code == 400

    def test_nonexistent_item_404(self, client, engine):
        resp = client.post("/api/alerts", json={
            "email": "a@b.com",
            "tracked_item_id": 999,
            "condition": "buy_now",
        })
        assert resp.status_code == 404

    def test_not_json_400(self, client):
        resp = client.post("/api/alerts", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/unsubscribe/<token>
# ---------------------------------------------------------------------------

class TestUnsubscribe:
    def test_valid_token(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(engine, "a@b.com", item["id"], "buy_now")

        resp = client.get(f"/api/unsubscribe/{alert['unsubscribe_token']}")
        assert resp.status_code == 200
        assert "unsubscribed" in resp.get_json()["message"].lower()

    def test_invalid_token(self, client):
        resp = client.get("/api/unsubscribe/bogus_token_123")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_double_unsubscribe_is_harmless(self, client, engine):
        """Clicking the unsubscribe link twice is safe — both return 200."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        alert = create_alert(engine, "a@b.com", item["id"], "buy_now")
        token = alert["unsubscribe_token"]

        resp1 = client.get(f"/api/unsubscribe/{token}")
        resp2 = client.get(f"/api/unsubscribe/{token}")
        assert resp1.status_code == 200
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/items/<id>
# ---------------------------------------------------------------------------

class TestItemDetail:
    def test_existing_item(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        insert_snapshots(engine, item["id"], [
            {"ebay_item_id": "v1|111|0", "title": "J4", "price": 200.0},
            {"ebay_item_id": "v1|222|0", "title": "J4 Used", "price": 180.0},
        ])
        insert_decision(engine, item["id"], "llm_reasoning",
                        action="wait", confidence=0.6, reasoning="Hold.")

        resp = client.get(f"/api/items/{item['id']}")
        assert resp.status_code == 200

        data = resp.get_json()
        assert data["tracked_item"]["search_query"] == "Jordan 4"
        assert data["snapshot_count"] == 2
        assert len(data["snapshots"]) == 2
        assert len(data["decisions"]) == 1
        assert data["status"] == "collecting"

    def test_nonexistent_item_404(self, client):
        resp = client.get("/api/items/999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_search_rate_limit(self, rate_limited_client, engine):
        # 3/minute limit — first 3 should pass, 4th should be blocked
        for i in range(3):
            get_or_create_tracked_item(engine, f"item{i}")
            resp = rate_limited_client.get(f"/api/search?q=item{i}")
            assert resp.status_code == 200

        get_or_create_tracked_item(engine, "item99")
        resp = rate_limited_client.get("/api/search?q=item99")
        assert resp.status_code == 429

    def test_alert_rate_limit(self, rate_limited_client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        for i in range(2):
            resp = rate_limited_client.post("/api/alerts", json={
                "email": f"user{i}@example.com",
                "tracked_item_id": item["id"],
                "condition": "buy_now",
            })
            assert resp.status_code == 201

        resp = rate_limited_client.post("/api/alerts", json={
            "email": "blocked@example.com",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Signals in /api/items/<id>
# ---------------------------------------------------------------------------

def _insert_batch(engine, item_id, batch_id, prices, time_offset_hours=0, condition=""):
    """Insert a batch of snapshots with distinct eBay item IDs."""
    t = datetime.now(timezone.utc) - timedelta(hours=time_offset_hours)
    rows = [
        {
            "ebay_item_id": f"v1|{batch_id}{i:04d}|0",
            "title": "Test Item",
            "price": p,
            "condition": condition,
            "poll_batch_id": batch_id,
            "snapshot_time": t,
        }
        for i, p in enumerate(prices)
    ]
    insert_snapshots(engine, item_id, rows, poll_batch_id=batch_id)


class TestItemDetailSignals:
    def test_item_detail_includes_signals(self, client, engine):
        """Endpoint returns a signals dict with expected TrendSignals fields."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "batch_a", [200, 210, 190], time_offset_hours=48)
        _insert_batch(engine, item["id"], "batch_b", [195, 205, 185], time_offset_hours=0)

        resp = client.get(f"/api/items/{item['id']}")
        assert resp.status_code == 200
        data = resp.get_json()

        assert "signals" in data
        signals = data["signals"]
        for key in (
            "sufficient_data", "latest_batch_median", "price_p25",
            "price_p75", "avg_price", "min_price", "max_price",
        ):
            assert key in signals, f"Missing key: {key}"

    def test_signals_match_compute_signals(self, client, engine):
        """API signals must exactly match compute_signals() output."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "batch_a", [200, 210, 190], time_offset_hours=48)
        _insert_batch(engine, item["id"], "batch_b", [195, 205, 185], time_offset_hours=0)

        resp = client.get(f"/api/items/{item['id']}")
        api_signals = resp.get_json()["signals"]

        direct_signals = compute_signals(engine, item["id"]).to_dict()

        # Compare all numeric/boolean fields (skip latest_batch_time — may drift by ms)
        for key in direct_signals:
            if key == "latest_batch_time":
                continue
            assert api_signals[key] == direct_signals[key], (
                f"Mismatch on '{key}': API={api_signals[key]}, direct={direct_signals[key]}"
            )

    def test_signals_present_even_with_insufficient_data(self, client, engine):
        """A single batch should still return signals with sufficient_data=False."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "batch_only", [200, 210], time_offset_hours=0)

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        assert "signals" in data
        assert data["signals"]["sufficient_data"] is False


# ---------------------------------------------------------------------------
# Timestamp serialization
# ---------------------------------------------------------------------------

class TestTimestampSerialization:
    def test_snapshot_timestamps_have_utc_suffix(self, client, engine):
        """All datetime fields must end with 'Z' so JS treats them as UTC."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        insert_snapshots(engine, item["id"], [
            {"ebay_item_id": "v1|111|0", "title": "J4", "price": 200.0},
        ])

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        # snapshot_time should end with Z
        snap = data["snapshots"][0]
        assert snap["snapshot_time"].endswith("Z"), (
            f"Expected UTC suffix, got: {snap['snapshot_time']}"
        )

    def test_tracked_item_timestamps_have_utc_suffix(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        created = data["tracked_item"]["created_at"]
        assert created.endswith("Z"), (
            f"Expected UTC suffix, got: {created}"
        )


# ---------------------------------------------------------------------------
# Condition-segmented signals in /api/items/<id>
# ---------------------------------------------------------------------------

class TestItemDetailConditions:
    def test_response_includes_signals_by_condition(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "ba", [200, 210, 190], 48, condition="New")
        _insert_batch(engine, item["id"], "bb", [195, 205, 185], 0, condition="New")

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        assert "signals_by_condition" in data
        assert "All" in data["signals_by_condition"]
        assert "New" in data["signals_by_condition"]

    def test_all_matches_signals_key(self, client, engine):
        """signals_by_condition['All'] must match the top-level signals key."""
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "ba", [200, 210], 48, condition="New")
        _insert_batch(engine, item["id"], "bb", [195, 205], 0, condition="New")

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        for key in ("avg_price", "snapshot_count", "sufficient_data"):
            assert data["signals"][key] == data["signals_by_condition"]["All"][key]

    def test_response_includes_listing_labels(self, client, engine):
        item, _, _ = get_or_create_tracked_item(engine, "Jordan 4")
        _insert_batch(engine, item["id"], "ba", [200, 210, 190], 48, condition="New")
        _insert_batch(engine, item["id"], "bb", [150, 250, 200], 0, condition="New")

        resp = client.get(f"/api/items/{item['id']}")
        data = resp.get_json()

        assert "listing_labels" in data
        assert isinstance(data["listing_labels"], list)
        # With sufficient data, at least some labels should be generated
        labels = {l["label"] for l in data["listing_labels"]}
        assert labels.issubset({"Good Buy", "Fair Price", "Overpriced"})

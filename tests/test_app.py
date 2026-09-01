"""Tests for the Flask API layer — all using test client, no real network."""

import json

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
    def test_new_search(self, client, engine):
        resp = client.get("/api/search?q=Jordan 4 Retro")
        assert resp.status_code == 200

        data = resp.get_json()
        assert data["created"] is True
        assert data["status"] == "collecting"
        assert data["snapshot_count"] == 0
        assert data["tracked_item"]["normalized_query"] == "jordan 4 retro"

    def test_existing_search(self, client, engine):
        get_or_create_tracked_item(engine, "Jordan 4 Retro")

        resp = client.get("/api/search?q=Jordan 4 Retro")
        data = resp.get_json()

        assert resp.status_code == 200
        assert data["created"] is False

    def test_returns_snapshots_and_decisions(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4 Retro")
        insert_snapshots(engine, item["id"], [
            {"ebay_item_id": "v1|111|0", "title": "J4", "price": 200.0},
        ])
        insert_decision(engine, item["id"], "llm_reasoning", action="wait")

        resp = client.get("/api/search?q=Jordan 4 Retro")
        data = resp.get_json()

        assert data["snapshot_count"] == 1
        assert len(data["snapshots"]) == 1
        assert len(data["decisions"]) == 1

    def test_dedupes_across_casing(self, client, engine):
        client.get("/api/search?q=Jordan 4 Retro")
        resp = client.get("/api/search?q=jordan 4 retro")
        assert resp.get_json()["created"] is False

    def test_empty_query_400(self, client):
        resp = client.get("/api/search?q=")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_missing_query_400(self, client):
        resp = client.get("/api/search")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/alerts
# ---------------------------------------------------------------------------

class TestCreateAlert:
    def test_create_price_alert(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

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
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "user@example.com",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })

        assert resp.status_code == 201

    def test_token_not_in_response(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "user@example.com",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })

        data = resp.get_json()
        assert "unsubscribe_token" not in data

    def test_missing_email_400(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })
        assert resp.status_code == 400

    def test_invalid_email_400(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

        resp = client.post("/api/alerts", json={
            "email": "not-an-email",
            "tracked_item_id": item["id"],
            "condition": "buy_now",
        })
        assert resp.status_code == 400

    def test_missing_condition_400(self, client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

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
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
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
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
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
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")
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
    def test_search_rate_limit(self, rate_limited_client):
        # 3/minute limit — first 3 should pass, 4th should be blocked
        for i in range(3):
            resp = rate_limited_client.get(f"/api/search?q=item{i}")
            assert resp.status_code == 200

        resp = rate_limited_client.get("/api/search?q=item99")
        assert resp.status_code == 429

    def test_alert_rate_limit(self, rate_limited_client, engine):
        item, _ = get_or_create_tracked_item(engine, "Jordan 4")

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

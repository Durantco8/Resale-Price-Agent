"""Tests for the eBay API client — all network calls are faked via DI."""

import time
from types import SimpleNamespace

import pytest

from resale_price_agent.ebay_client import (
    EbayClient,
    EbayTokenFetcher,
    ListingSnapshot,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN_RESPONSE = {
    "access_token": "v^1.1#fake_token_abc123",
    "expires_in": 7200,
    "token_type": "Application Access Token",
}

FAKE_SEARCH_RESPONSE = {
    "total": 2,
    "itemSummaries": [
        {
            "itemId": "v1|111111111111|0",
            "title": "Jordan 4 Retro Military Black - Size 10",
            "price": {"value": "219.99", "currency": "USD"},
            "condition": "New with box",
            "seller": {"feedbackScore": 5432},
            "itemWebUrl": "https://www.ebay.com/itm/111111111111",
            "shippingOptions": [
                {"shippingCost": {"value": "14.95", "currency": "USD"}}
            ],
            "itemLocation": {
                "city": "Portland",
                "stateOrProvince": "OR",
                "country": "US",
            },
            "buyingOptions": ["FIXED_PRICE"],
            "itemCreationDate": "2026-08-30T12:00:00.000Z",
        },
        {
            "itemId": "v1|222222222222|0",
            "title": "Air Jordan 4 Military Black Mens 10 DS",
            "price": {"value": "205.00", "currency": "USD"},
            "condition": "New with box",
            "seller": {"feedbackScore": 128},
            "itemWebUrl": "https://www.ebay.com/itm/222222222222",
            "shippingOptions": [],
            "itemLocation": {"country": "US"},
            "buyingOptions": ["AUCTION"],
            "itemCreationDate": "2026-08-29T08:30:00.000Z",
        },
    ],
}


def _make_fake_response(json_body, status_code=200):
    """Build an object that quacks like ``requests.Response``."""
    resp = SimpleNamespace()
    resp.status_code = status_code
    resp.json = lambda: json_body
    resp.raise_for_status = lambda: None
    if status_code >= 400:
        resp.raise_for_status = _raise_http_error
    return resp


def _raise_http_error():
    from requests.exceptions import HTTPError
    raise HTTPError("Mocked HTTP error")


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------

class TestEbayTokenFetcher:
    def test_fetches_token_on_first_call(self):
        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            return _make_fake_response(FAKE_TOKEN_RESPONSE)

        fetcher = EbayTokenFetcher(
            client_id="test_id",
            client_secret="test_secret",
            http_post=fake_post,
        )
        token = fetcher.get_token()

        assert token == "v^1.1#fake_token_abc123"
        assert len(calls) == 1

    def test_caches_token_on_second_call(self):
        call_count = 0

        def fake_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_fake_response(FAKE_TOKEN_RESPONSE)

        fetcher = EbayTokenFetcher(
            client_id="test_id",
            client_secret="test_secret",
            http_post=fake_post,
        )
        fetcher.get_token()
        fetcher.get_token()

        assert call_count == 1  # second call used cache

    def test_refreshes_when_expired(self):
        call_count = 0

        def fake_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_fake_response(FAKE_TOKEN_RESPONSE)

        fetcher = EbayTokenFetcher(
            client_id="test_id",
            client_secret="test_secret",
            http_post=fake_post,
        )
        fetcher.get_token()
        # Force expiry by backdating _expires_at
        fetcher._expires_at = time.time() - 1
        fetcher.get_token()

        assert call_count == 2  # had to re-fetch

    def test_refreshes_within_60s_buffer(self):
        call_count = 0

        def fake_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_fake_response(FAKE_TOKEN_RESPONSE)

        fetcher = EbayTokenFetcher(
            client_id="test_id",
            client_secret="test_secret",
            http_post=fake_post,
        )
        fetcher.get_token()
        # Set expiry to 30 seconds from now (inside the 60s buffer)
        fetcher._expires_at = time.time() + 30
        fetcher.get_token()

        assert call_count == 2

    def test_raises_on_auth_failure(self):
        def fake_post(url, **kwargs):
            return _make_fake_response({}, status_code=401)

        fetcher = EbayTokenFetcher(
            client_id="bad_id",
            client_secret="bad_secret",
            http_post=fake_post,
        )
        with pytest.raises(Exception):
            fetcher.get_token()


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestEbayClient:
    _sentinel = object()

    def _build_client(self, search_response=_sentinel):
        """Build an EbayClient with a pre-loaded fake token and fake HTTP."""
        fetcher = EbayTokenFetcher(
            client_id="id",
            client_secret="secret",
            http_post=lambda *a, **kw: _make_fake_response(
                FAKE_TOKEN_RESPONSE
            ),
        )
        fetcher.get_token()  # prime the cache

        body = (
            FAKE_SEARCH_RESPONSE
            if search_response is self._sentinel
            else search_response
        )

        def fake_get(url, **kwargs):
            return _make_fake_response(body)

        return EbayClient(
            token_fetcher=fetcher,
            http_get=fake_get,
        )

    def test_search_returns_listing_snapshots(self):
        client = self._build_client()
        results = client.search_listings("Jordan 4 Military Black size 10")

        assert len(results) == 2
        assert all(isinstance(r, ListingSnapshot) for r in results)

    def test_first_listing_fields(self):
        client = self._build_client()
        results = client.search_listings("Jordan 4 Military Black size 10")
        first = results[0]

        assert first.item_id == "v1|111111111111|0"
        assert first.price_amount == 219.99
        assert first.price_currency == "USD"
        assert first.condition == "New with box"
        assert first.seller_feedback_score == 5432
        assert first.shipping_cost == 14.95
        assert first.item_location == "Portland, OR, US"
        assert first.buying_options == ["FIXED_PRICE"]
        assert "111111111111" in first.item_url

    def test_second_listing_missing_shipping(self):
        client = self._build_client()
        results = client.search_listings("Jordan 4 Military Black size 10")
        second = results[1]

        assert second.shipping_cost is None
        assert second.item_location == "US"
        assert second.buying_options == ["AUCTION"]

    def test_empty_response(self):
        client = self._build_client(search_response={"itemSummaries": []})
        results = client.search_listings("nonexistent item")
        assert results == []

    def test_missing_item_summaries_key(self):
        client = self._build_client(search_response={})
        results = client.search_listings("nonexistent item")
        assert results == []

    def test_api_error_raises(self):
        fetcher = EbayTokenFetcher(
            client_id="id",
            client_secret="secret",
            http_post=lambda *a, **kw: _make_fake_response(
                FAKE_TOKEN_RESPONSE
            ),
        )
        fetcher.get_token()

        def fake_get(url, **kwargs):
            return _make_fake_response({}, status_code=500)

        client = EbayClient(token_fetcher=fetcher, http_get=fake_get)
        with pytest.raises(Exception):
            client.search_listings("anything")

    def test_passes_query_and_limit_params(self):
        """Verify the correct params are forwarded to the HTTP call."""
        fetcher = EbayTokenFetcher(
            client_id="id",
            client_secret="secret",
            http_post=lambda *a, **kw: _make_fake_response(
                FAKE_TOKEN_RESPONSE
            ),
        )
        fetcher.get_token()

        captured = {}

        def fake_get(url, **kwargs):
            captured.update(kwargs)
            return _make_fake_response(FAKE_SEARCH_RESPONSE)

        client = EbayClient(token_fetcher=fetcher, http_get=fake_get)
        client.search_listings("Jordan 4 size 10", limit=25)

        assert captured["params"]["q"] == "Jordan 4 size 10"
        assert captured["params"]["limit"] == "25"
        assert "Bearer" in captured["headers"]["Authorization"]

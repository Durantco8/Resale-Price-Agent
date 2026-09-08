"""eBay Browse API client with OAuth client-credentials flow.

Designed for dependency injection: pass in a ``token_fetcher`` and
``http_client`` so callers (and tests) can swap in fakes without
touching production code paths.
"""

import time
from dataclasses import dataclass

import requests

from resale_price_agent.config import (
    EBAY_AUTH_URL,
    EBAY_BROWSE_URL,
    EBAY_CLIENT_ID,
    EBAY_CLIENT_SECRET,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ListingSnapshot:
    item_id: str
    title: str
    price_amount: float
    price_currency: str
    condition: str
    seller_feedback_score: int
    item_url: str
    shipping_cost: float | None
    item_location: str | None
    buying_options: list[str]
    snapshot_time: str  # ISO-8601 string from the API or our own timestamp
    image_url: str | None = None


# ---------------------------------------------------------------------------
# OAuth token management
# ---------------------------------------------------------------------------

class EbayTokenFetcher:
    """Fetches and caches an OAuth client-credentials token."""

    def __init__(
        self,
        client_id: str = EBAY_CLIENT_ID,
        client_secret: str = EBAY_CLIENT_SECRET,
        auth_url: str = EBAY_AUTH_URL,
        http_post=None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._auth_url = auth_url
        self._http_post = http_post or requests.post
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        """Return a valid token, refreshing if expired or about to expire."""
        # Refresh 60 seconds before actual expiry to avoid edge-case failures
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        return self._refresh()

    def _refresh(self) -> str:
        resp = self._http_post(
            self._auth_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            auth=(self._client_id, self._client_secret),
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + body["expires_in"]
        return self._token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_listing_url(item_id: str) -> str:
    """Build a direct eBay listing URL from an API item ID.

    The Browse API returns IDs like ``v1|123456789012|0``.  The middle
    segment is the actual listing number used in ``/itm/`` URLs.
    """
    parts = item_id.split("|")
    listing_id = parts[1] if len(parts) >= 2 else item_id
    return f"https://www.ebay.com/itm/{listing_id}"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class EbayClient:
    """Wraps the Browse API ``item_summary/search`` endpoint."""

    def __init__(
        self,
        token_fetcher: EbayTokenFetcher | None = None,
        browse_url: str = EBAY_BROWSE_URL,
        http_get=None,
    ):
        self._token_fetcher = token_fetcher or EbayTokenFetcher()
        self._browse_url = browse_url
        self._http_get = http_get or requests.get

    def search_listings(
        self, query: str, limit: int = 50,
        category_ids: str | None = None,
    ) -> list[ListingSnapshot]:
        token = self._token_fetcher.get_token()
        params = {"q": query, "limit": str(limit)}
        if category_ids:
            params["category_ids"] = category_ids
        resp = self._http_get(
            self._browse_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params,
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    @staticmethod
    def _parse_response(data: dict) -> list[ListingSnapshot]:
        items = data.get("itemSummaries", [])
        results: list[ListingSnapshot] = []
        for item in items:
            price_info = item.get("price", {})
            shipping = item.get("shippingOptions", [{}])
            shipping_cost_raw = (
                shipping[0].get("shippingCost", {}).get("value")
                if shipping
                else None
            )
            location = item.get("itemLocation", {})
            location_str = None
            if location:
                parts = [
                    location.get("city", ""),
                    location.get("stateOrProvince", ""),
                    location.get("country", ""),
                ]
                location_str = ", ".join(p for p in parts if p) or None

            results.append(
                ListingSnapshot(
                    item_id=item.get("itemId", ""),
                    title=item.get("title", ""),
                    price_amount=float(price_info.get("value", 0)),
                    price_currency=price_info.get("currency", "USD"),
                    condition=item.get("condition", ""),
                    seller_feedback_score=int(
                        item.get("seller", {}).get("feedbackScore", 0)
                    ),
                    item_url=_build_listing_url(item.get("itemId", "")),
                    shipping_cost=(
                        float(shipping_cost_raw)
                        if shipping_cost_raw is not None
                        else None
                    ),
                    item_location=location_str,
                    buying_options=item.get("buyingOptions", []),
                    snapshot_time=item.get(
                        "itemCreationDate", ""
                    ),
                    image_url=item.get("image", {}).get("imageUrl"),
                )
            )
        return results

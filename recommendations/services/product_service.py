import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class EbayService:
    """eBay Browse API (OAuth2 client-credentials) item_summary search."""

    TOKEN_CACHE_KEY = "ebay:app_token"
    TOKEN_SAFETY_WINDOW = 60  # refresh 60s before expiry

    @classmethod
    def _get_token(cls) -> str | None:
        if not settings.EBAY_CLIENT_ID or not settings.EBAY_CLIENT_SECRET:
            return None

        cached = cache.get(cls.TOKEN_CACHE_KEY)
        if cached:
            return cached

        try:
            r = requests.post(
                settings.EBAY_OAUTH_URL,
                auth=(settings.EBAY_CLIENT_ID, settings.EBAY_CLIENT_SECRET),
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:
            logger.exception("eBay OAuth error: %s", exc)
            return None

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 7200))
        if token:
            cache.set(
                cls.TOKEN_CACHE_KEY,
                token,
                max(60, expires_in - cls.TOKEN_SAFETY_WINDOW),
            )
        return token

    @classmethod
    def search(cls, keyword: str, max_items: int = 5) -> list:
        token = cls._get_token()
        if not token:
            logger.warning("eBay credentials missing — skipping eBay search.")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": settings.EBAY_MARKETPLACE_ID,
            "Accept": "application/json",
        }
        params = {
            "q": keyword,
            "limit": str(max_items),
            "sort": "price",
            "filter": "buyingOptions:{FIXED_PRICE}",
        }

        try:
            r = requests.get(
                settings.EBAY_BROWSE_URL,
                headers=headers,
                params=params,
                timeout=15,
            )
            if r.status_code == 401:
                # Token expired mid-flight; drop it and retry once.
                cache.delete(cls.TOKEN_CACHE_KEY)
                token = cls._get_token()
                if not token:
                    return []
                headers["Authorization"] = f"Bearer {token}"
                r = requests.get(
                    settings.EBAY_BROWSE_URL,
                    headers=headers,
                    params=params,
                    timeout=15,
                )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.exception("eBay API error: %s", exc)
            return []

        products = []
        for item in data.get("itemSummaries", []) or []:
            try:
                price = None
                if item.get("price") and item["price"].get("value") is not None:
                    price = float(item["price"]["value"])

                image_url = (
                    (item.get("image") or {}).get("imageUrl")
                    or ((item.get("thumbnailImages") or [{}])[0]).get("imageUrl")
                    or ""
                )

                seller = item.get("seller") or {}
                rating = (
                    float(seller["feedbackPercentage"]) / 100.0
                    if seller.get("feedbackPercentage")
                    else None
                )

                products.append({
                    "source": "ebay",
                    "title": (item.get("title") or "Untitled")[:490],
                    "url": item.get("itemWebUrl") or "",
                    "image_url": image_url,
                    "price_usd": price,
                    "rating": rating,
                })
            except Exception as exc:
                logger.debug("Skipping eBay item: %s", exc)

        return products


class ShopifyService:
    """Unchanged — searches curated partner Shopify stores via /products.json."""

    @staticmethod
    def search(keyword: str, max_per_store: int = 20) -> list:
        stores = settings.SHOPIFY_STORES
        if not stores:
            logger.info("No SHOPIFY_STORES configured — skipping.")
            return []

        products = []
        keywords = [w.lower() for w in keyword.split() if len(w) > 2]

        for store in stores:
            try:
                r = requests.get(
                    f"{store.rstrip('/')}/products.json",
                    params={"limit": max_per_store},
                    timeout=10,
                )
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                logger.warning("Shopify store %s failed: %s", store, exc)
                continue

            for p in data.get("products", []):
                title = (p.get("title") or "").lower()
                if keywords and not any(k in title for k in keywords):
                    continue
                try:
                    variant = p["variants"][0]
                    price = float(variant.get("price") or 0) or None
                except Exception:
                    price = None

                images = p.get("images") or []
                products.append({
                    "source": "shopify",
                    "title": p.get("title", "Untitled")[:490],
                    "url": f"{store.rstrip('/')}/products/{p.get('handle', '')}",
                    "image_url": images[0]["src"] if images else "",
                    "price_usd": price,
                    "rating": None,
                })
        return products[:10]


class AliExpressService:
    """Unchanged stub."""

    ENDPOINT = "https://api-sg.aliexpress.com/sync"

    @staticmethod
    def search(keyword: str, max_items: int = 5) -> list:
        if not settings.ALIEXPRESS_APP_KEY or not settings.ALIEXPRESS_APP_SECRET:
            logger.info("AliExpress credentials missing — skipping.")
            return []
        return []
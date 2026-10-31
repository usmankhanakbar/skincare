import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AmazonService:
    """Amazon Product Advertising API 5.0."""

    @staticmethod
    def search(keyword: str, max_items: int = 5) -> list:
        if not all(
            [settings.AMAZON_ACCESS_KEY, settings.AMAZON_SECRET_KEY, settings.AMAZON_PARTNER_TAG]
        ):
            logger.warning("Amazon credentials missing — skipping Amazon search.")
            return []

        try:
            from amazon_paapi import AmazonApi
            amazon = AmazonApi(
                settings.AMAZON_ACCESS_KEY,
                settings.AMAZON_SECRET_KEY,
                settings.AMAZON_PARTNER_TAG,
                settings.AMAZON_REGION,
            )
            result = amazon.search_items(keywords=keyword, item_count=max_items)
        except Exception as exc:
            logger.exception("Amazon API error: %s", exc)
            return []

        products = []
        for item in getattr(result, "items", []) or []:
            try:
                title = item.item_info.title.display_value if item.item_info else "Untitled"
                price = None
                rating = None
                if getattr(item, "offers", None) and item.offers.listings:
                    listing = item.offers.listings[0]
                    if listing.price:
                        price = float(listing.price.amount)
                if getattr(item, "customer_reviews", None):
                    rating = item.customer_reviews.star_rating.value if item.customer_reviews.star_rating else None

                products.append({
                    "source": "amazon",
                    "title": title[:490],
                    "url": item.detail_page_url,
                    "image_url": (
                        item.images.primary.large.url
                        if getattr(item, "images", None) and item.images.primary
                        else ""
                    ),
                    "price_usd": price,
                    "rating": rating,
                })
            except Exception as exc:
                logger.debug("Skipping Amazon item: %s", exc)
        return products


class ShopifyService:
    """Searches curated partner Shopify stores via public /products.json."""

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
    """AliExpress affiliate API — requires approved app credentials.

    If credentials are not set, returns an empty list so the app still works.
    """

    ENDPOINT = "https://api-sg.aliexpress.com/sync"

    @staticmethod
    def search(keyword: str, max_items: int = 5) -> list:
        if not settings.ALIEXPRESS_APP_KEY or not settings.ALIEXPRESS_APP_SECRET:
            logger.info("AliExpress credentials missing — skipping.")
            return []

        # NOTE: Full SigV4-style HMAC-SHA256 signing required. This is a stub
        # so the app works end-to-end; plug in a proper signed call when you have
        # approved affiliate credentials.
        try:
            params = {
                "method": "aliexpress.affiliate.product.query",
                "app_key": settings.ALIEXPRESS_APP_KEY,
                "keywords": keyword,
                "page_size": max_items,
                "tracking_id": settings.ALIEXPRESS_TRACKING_ID,
                "target_currency": "USD",
                "target_language": "EN",
                "sign_method": "sha256",
                "timestamp": "",  # set to ms epoch
                "format": "json",
                "v": "2.0",
            }
            # sign = hmac_sha256(app_secret, concatenated_sorted_params)
            # params["sign"] = sign
            # resp = requests.post(AliExpressService.ENDPOINT, data=params, timeout=15)
            # ...parse and return products...
        except Exception as exc:
            logger.exception("AliExpress error: %s", exc)

        return []
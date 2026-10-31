import logging
from concurrent.futures import ThreadPoolExecutor

from .deepseek_service import DeepSeekService
from .product_service import AmazonService, AliExpressService, ShopifyService
from .youtube_service import YouTubeService
from ..models import SkinIssue, Recommendation, Product, VideoResource

logger = logging.getLogger(__name__)


class RecommendationOrchestrator:

    @staticmethod
    def process(skin_issue: SkinIssue) -> Recommendation:
        # 1. Ask DeepSeek
        ai = DeepSeekService.get_recommendation(
            skin_issue.description, skin_issue.skin_type, skin_issue.age_range
        )

        # 2. Save Recommendation
        rec = Recommendation.objects.create(
            skin_issue=skin_issue,
            analysis=ai.get("analysis", ""),
            ingredients_to_look_for=ai.get("ingredients_to_look_for", []),
            ingredients_to_avoid=ai.get("ingredients_to_avoid", []),
            product_categories=ai.get("product_categories", []),
            routine_steps=ai.get("routine_steps", []),
            price_range_usd=ai.get("price_range_usd", {}),
            safety_note=ai.get("safety_note", ""),
            raw_ai_response=ai,
        )

        keywords = (ai.get("search_keywords") or [])[:3]
        if not keywords:
            keywords = [skin_issue.description[:60]]

        # 3. Fetch products + videos in parallel
        with ThreadPoolExecutor(max_workers=4) as ex:
            amazon_futures = [ex.submit(AmazonService.search, k) for k in keywords]
            shopify_futures = [ex.submit(ShopifyService.search, k) for k in keywords]
            aliexpress_futures = [ex.submit(AliExpressService.search, k) for k in keywords]
            yt_future = ex.submit(
                YouTubeService.search,
                ai.get("youtube_search_query", skin_issue.description[:80]),
            )

            seen_urls = set()

            def save_products(futures, source):
                for fut in futures:
                    try:
                        for p in fut.result():
                            if p["url"] in seen_urls:
                                continue
                            seen_urls.add(p["url"])
                            Product.objects.create(recommendation=rec, **p)
                    except Exception as exc:
                        logger.warning("%s fetch failed: %s", source, exc)

            save_products(amazon_futures, "Amazon")
            save_products(shopify_futures, "Shopify")
            save_products(aliexpress_futures, "AliExpress")

            try:
                for v in yt_future.result():
                    VideoResource.objects.create(recommendation=rec, **v)
            except Exception as exc:
                logger.warning("YouTube fetch failed: %s", exc)

        return rec
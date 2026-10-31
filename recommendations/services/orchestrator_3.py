import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import connection, transaction

from .ollama_service import OllamaService, OllamaError
from .product_service import AmazonService, AliExpressService, ShopifyService
from .youtube_service import YouTubeService
from ..models import SkinIssue, Recommendation, Product, VideoResource

logger = logging.getLogger(__name__)

MAX_URL_LEN = 1000


def _search_and_close(fn, *args):
    """Run a provider search in a thread, then close that thread's DB connection."""
    try:
        return fn(*args)
    finally:
        connection.close()


class RecommendationOrchestrator:

    MAX_KEYWORDS = 3
    MAX_WORKERS = 6

    @classmethod
    def process(cls, skin_issue: SkinIssue) -> Recommendation:
        # 1. Ask Ollama ---------------------------------------------------
        ai = OllamaService.get_recommendation(
            skin_issue.description,
            skin_issue.skin_type,
            skin_issue.age_range,
        )

        # 2. Save Recommendation (idempotent per SkinIssue) ---------------
        rec, _created = Recommendation.objects.update_or_create(
            skin_issue=skin_issue,
            defaults={
                "analysis": ai.get("analysis", ""),
                "ingredients_to_look_for": ai.get("ingredients_to_look_for", []),
                "ingredients_to_avoid": ai.get("ingredients_to_avoid", []),
                "product_categories": ai.get("product_categories", []),
                "routine_steps": ai.get("routine_steps", []),
                "price_range_usd": ai.get("price_range_usd", {}),
                "safety_note": ai.get("safety_note", ""),
                "raw_ai_response": ai,
            },
        )

        if not _created:
            # Re-run: clear old children so we don't accumulate duplicates
            rec.products.all().delete()
            rec.videos.all().delete()

        # 3. Keywords ------------------------------------------------------
        keywords = [k for k in (ai.get("search_keywords") or []) if k][: cls.MAX_KEYWORDS]
        if not keywords:
            keywords = [skin_issue.description[:60]]

        # 4. Fan out -------------------------------------------------------
        with ThreadPoolExecutor(max_workers=cls.MAX_WORKERS) as ex:
            product_futures = {}
            for k in keywords:
                product_futures[ex.submit(_search_and_close, AmazonService.search, k)] = "Amazon"
                product_futures[ex.submit(_search_and_close, ShopifyService.search, k)] = "Shopify"
                product_futures[ex.submit(_search_and_close, AliExpressService.search, k)] = "AliExpress"

            yt_future = ex.submit(
                _search_and_close,
                YouTubeService.search,
                ai.get("youtube_search_query") or skin_issue.description[:80],
            )

            cls._save_products(rec, product_futures)
            cls._save_videos(rec, yt_future)

        return rec

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _save_products(rec: Recommendation, futures: dict) -> None:
        seen_urls: set[str] = set()
        pending: list[Product] = []

        for fut in as_completed(futures):
            source = futures[fut]
            try:
                items = fut.result() or []
            except Exception as exc:
                logger.warning("%s fetch failed: %s", source, exc)
                continue

            for item in items:
                url = item.get("url")
                if not url or len(url) > MAX_URL_LEN or url in seen_urls:
                    continue
                seen_urls.add(url)

                if item.get("image_url") and len(item["image_url"]) > MAX_URL_LEN:
                    item["image_url"] = item["image_url"][:MAX_URL_LEN]
                if item.get("title") and len(item["title"]) > 500:
                    item["title"] = item["title"][:500]

                pending.append(Product(recommendation=rec, **item))

        if pending:
            with transaction.atomic():
                Product.objects.bulk_create(pending, ignore_conflicts=True)
            logger.info("Saved %d products for rec=%s", len(pending), rec.pk)

    @staticmethod
    def _save_videos(rec: Recommendation, yt_future) -> None:
        try:
            videos = yt_future.result() or []
        except Exception as exc:
            logger.warning("YouTube fetch failed: %s", exc)
            return

        seen_urls: set[str] = set()
        pending: list[VideoResource] = []

        for v in videos:
            url = v.get("url")
            if not url or len(url) > MAX_URL_LEN or url in seen_urls:
                continue
            seen_urls.add(url)

            if v.get("thumbnail_url") and len(v["thumbnail_url"]) > MAX_URL_LEN:
                v["thumbnail_url"] = v["thumbnail_url"][:MAX_URL_LEN]
            if v.get("title") and len(v["title"]) > 500:
                v["title"] = v["title"][:500]
            if v.get("channel") and len(v["channel"]) > 200:
                v["channel"] = v["channel"][:200]

            pending.append(VideoResource(recommendation=rec, **v))

        if pending:
            with transaction.atomic():
                VideoResource.objects.bulk_create(pending, ignore_conflicts=True)
            logger.info("Saved %d videos for rec=%s", len(pending), rec.pk)
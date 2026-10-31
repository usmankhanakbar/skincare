import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class YouTubeService:
    ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

    @staticmethod
    def search(query: str, max_results: int = 3) -> list:
        if not settings.YOUTUBE_API_KEY:
            logger.warning("YOUTUBE_API_KEY missing — skipping YouTube search.")
            return []

        params = {
            "part": "snippet",
            "q": f"{query} skincare",
            "maxResults": max_results,
            "type": "video",
            "relevanceLanguage": "en",
            "safeSearch": "moderate",
            "key": settings.YOUTUBE_API_KEY,
        }

        try:
            r = requests.get(YouTubeService.ENDPOINT, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.exception("YouTube API error: %s", exc)
            return []

        videos = []
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            if not vid:
                continue
            sn = item["snippet"]
            videos.append({
                "title": sn["title"][:490],
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail_url": sn["thumbnails"]["medium"]["url"],
                "channel": sn["channelTitle"][:190],
            })
        return videos
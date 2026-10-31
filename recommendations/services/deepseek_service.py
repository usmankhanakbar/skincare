import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class DeepSeekService:
    """Handles communication with the DeepSeek chat completion API."""

    SYSTEM_PROMPT = """You are a professional dermatology-informed skincare advisor
specializing in women's and girls' skin health. You provide safe, evidence-based,
culturally sensitive recommendations.

RULES:
- NEVER diagnose medical conditions.
- ALWAYS advise seeing a dermatologist for serious or persistent issues.
- Consider pregnancy/breastfeeding safety where relevant.
- Prefer affordable, widely available products.

Return ONLY valid JSON (no markdown, no code fences) in EXACTLY this structure:
{
  "analysis": "Brief warm analysis of the issue (2-4 sentences).",
  "ingredients_to_look_for": ["niacinamide", "salicylic acid"],
  "ingredients_to_avoid": ["denatured alcohol", "fragrance"],
  "product_categories": ["gentle cleanser", "oil-free moisturizer"],
  "routine_steps": [
    {"step": 1, "name": "Cleanse", "description": "..."},
    {"step": 2, "name": "Treat", "description": "..."},
    {"step": 3, "name": "Moisturize", "description": "..."},
    {"step": 4, "name": "Protect", "description": "..."}
  ],
  "price_range_usd": {"min": 15, "max": 80},
  "search_keywords": ["salicylic acid cleanser", "oil free moisturizer"],
  "youtube_search_query": "best skincare routine for oily acne prone skin",
  "safety_note": "See a dermatologist if the condition worsens or does not improve in 4 weeks."
}"""

    @classmethod
    def get_recommendation(cls, description: str, skin_type: str, age_range: str = "") -> dict:
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured in .env")

        user_prompt = (
            f"Skin type: {skin_type}\n"
            f"Age range: {age_range or 'not specified'}\n"
            f"User's issue: {description}\n\n"
            "Provide personalized skincare recommendations in the JSON format specified."
        )

        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        logger.info("Calling DeepSeek API for skin_type=%s", skin_type)
        resp = requests.post(
            settings.DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try to extract the JSON object
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
            raise
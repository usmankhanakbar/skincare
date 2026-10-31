from django.db import models
from django.contrib.auth.models import User


class SkinIssue(models.Model):
    SKIN_TYPES = [
        ("oily", "Oily"),
        ("dry", "Dry"),
        ("combination", "Combination"),
        ("sensitive", "Sensitive"),
        ("normal", "Normal"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField(help_text="Describe your skin issue")
    skin_type = models.CharField(max_length=20, choices=SKIN_TYPES)
    age_range = models.CharField(max_length=20, blank=True)
    image = models.ImageField(upload_to="skin_images/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} - {self.skin_type} - {self.description[:40]}"


class Recommendation(models.Model):
    skin_issue = models.OneToOneField(
        SkinIssue, on_delete=models.CASCADE, related_name="recommendation"
    )
    analysis = models.TextField(blank=True)
    ingredients_to_look_for = models.JSONField(default=list, blank=True)
    ingredients_to_avoid = models.JSONField(default=list, blank=True)
    product_categories = models.JSONField(default=list, blank=True)
    routine_steps = models.JSONField(default=list, blank=True)
    price_range_usd = models.JSONField(default=dict, blank=True)
    safety_note = models.TextField(blank=True)
    raw_ai_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recommendation for issue #{self.skin_issue_id}"


class Product(models.Model):
    SOURCES = [
        ("amazon", "Amazon"),
        ("shopify", "Shopify"),
        ("aliexpress", "AliExpress"),
    ]
    recommendation = models.ForeignKey(
        Recommendation, on_delete=models.CASCADE, related_name="products"
    )
    source = models.CharField(max_length=20, choices=SOURCES)
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    image_url = models.URLField(max_length=1000, blank=True)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [models.F("price_usd").asc(nulls_last=True)]
        constraints = [
            models.UniqueConstraint(
                fields=["recommendation", "url"],
                name="uniq_product_per_recommendation",
            ),
        ]

    def __str__(self):
        return f"[{self.source}] {self.title[:60]}"


class VideoResource(models.Model):
    recommendation = models.ForeignKey(
        Recommendation, on_delete=models.CASCADE, related_name="videos"
    )
    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    channel = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recommendation", "url"],
                name="uniq_video_per_recommendation",
            ),
        ]

    def __str__(self):
        return self.title[:80]
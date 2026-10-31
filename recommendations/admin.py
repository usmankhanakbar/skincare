from django.contrib import admin
from .models import SkinIssue, Recommendation, Product, VideoResource


@admin.register(SkinIssue)
class SkinIssueAdmin(admin.ModelAdmin):
    list_display = ("id", "skin_type", "age_range", "created_at")
    list_filter = ("skin_type",)
    search_fields = ("description",)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "skin_issue", "created_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "title", "price_usd")
    list_filter = ("source",)


@admin.register(VideoResource)
class VideoResourceAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "channel")
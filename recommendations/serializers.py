from rest_framework import serializers
from .models import SkinIssue, Recommendation, Product, VideoResource


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "source", "title", "url", "image_url", "price_usd", "rating"]


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoResource
        fields = ["id", "title", "url", "thumbnail_url", "channel"]


class RecommendationSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    videos = VideoSerializer(many=True, read_only=True)

    class Meta:
        model = Recommendation
        fields = [
            "id",
            "analysis",
            "ingredients_to_look_for",
            "ingredients_to_avoid",
            "product_categories",
            "routine_steps",
            "price_range_usd",
            "safety_note",
            "products",
            "videos",
            "created_at",
        ]


class SkinIssueSerializer(serializers.ModelSerializer):
    recommendation = RecommendationSerializer(read_only=True)

    class Meta:
        model = SkinIssue
        fields = [
            "id",
            "description",
            "skin_type",
            "age_range",
            "image",
            "created_at",
            "recommendation",
        ]
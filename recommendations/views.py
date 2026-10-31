import logging

from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SkinIssue
from .serializers import SkinIssueSerializer
from .services.ollama_service import OllamaError
from .services.orchestrator import RecommendationOrchestrator

logger = logging.getLogger(__name__)


def home(request):
    """Renders the single-page frontend."""
    return render(request, "recommendations/index.html")


@api_view(["POST"])
def analyze_skin(request):
    serializer = SkinIssueSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = request.user if request.user.is_authenticated else None
    issue = serializer.save(user=user)

    try:
        RecommendationOrchestrator.process(issue)
    except OllamaError as exc:
        logger.warning("Ollama failed for issue=%s: %s", issue.pk, exc)
        return Response(
            {"error": f"The skincare assistant is unavailable right now. {exc}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("Orchestrator failed for issue=%s", issue.pk)
        return Response(
            {"error": "Analysis failed. Please try again shortly."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    issue = (
        SkinIssue.objects
        .select_related("recommendation")
        .prefetch_related("recommendation__products", "recommendation__videos")
        .get(pk=issue.pk)
    )
    return Response(SkinIssueSerializer(issue).data, status=status.HTTP_201_CREATED)
import logging
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SkinIssue
from .serializers import SkinIssueSerializer
from .services.orchestrator_1 import RecommendationOrchestrator

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
    except Exception as exc:
        logger.exception("Orchestrator failed: %s", exc)
        return Response(
            {"error": f"Analysis failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    issue.refresh_from_db()
    return Response(SkinIssueSerializer(issue).data, status=status.HTTP_201_CREATED)
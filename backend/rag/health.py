from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from knowledge.models import KnowledgeEntry, LegalCategory

from .llm import get_llm_model, get_llm_provider, is_llm_enabled


@api_view(["GET"])
def health(request):
    try:
        knowledge_entries_count = KnowledgeEntry.objects.count()
        categories_count = LegalCategory.objects.count()
        chroma_indexed_entries_count = KnowledgeEntry.objects.exclude(
            embedding_id=""
        ).count()
    except Exception:
        return Response(
            {
                "status": "error",
                "database": "error",
                "message": "Le service de santé LexIA est temporairement indisponible.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    provider = get_llm_provider()
    return Response(
        {
            "status": "ok",
            "database": "ok",
            "knowledge_entries_count": knowledge_entries_count,
            "categories_count": categories_count,
            "chroma_indexed_entries_count": chroma_indexed_entries_count,
            "llm_enabled": is_llm_enabled(),
            "llm_provider": provider,
            "llm_model": get_llm_model(provider),
        }
    )

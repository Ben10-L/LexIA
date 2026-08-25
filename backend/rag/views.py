import uuid
from time import perf_counter

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .pipeline import FALLBACK_ANSWER, run_rag_pipeline


LEGAL_WARNING = (
    "Les informations fournies par LexIA sont destinées à un usage informatif "
    "uniquement et ne constituent pas un avis juridique officiel."
)
DARJA_LEGAL_WARNING = (
    "المعلومات اللي كتعطي LexIA هي غير للتوجيه والمعلومة العامة، وما كتعتبرش "
    "استشارة قانونية رسمية، وما كتبدلش استشارة محامي أو موثق أو سلطة مختصة."
)
ARABIC_LEGAL_WARNING = (
    "المعلومات التي تقدمها LexIA مخصصة للتوجيه والمعلومة العامة فقط، ولا تشكل "
    "استشارة قانونية رسمية، ولا تعوض استشارة محام أو موثق أو جهة مختصة."
)


@api_view(["GET"])
def home(request):
    return Response(
        {
            "name": "LexIA API",
            "status": "ok",
            "description": "Assistant d’orientation juridique marocaine.",
        }
    )


def get_response_metadata(answer_mode, sources):
    used_hybrid_retrieval = answer_mode in {"structured", "llm"} and bool(sources)
    if answer_mode == "llm" and sources:
        confidence = "high"
    elif answer_mode == "structured" and sources:
        confidence = "medium"
    elif answer_mode == "fallback":
        confidence = "low"
    else:
        confidence = "none"

    return {
        "confidence": confidence,
        "retrieval_method": "hybrid" if used_hybrid_retrieval else "none",
    }


@api_view(["POST"])
def chat(request):
    started_at = perf_counter()
    question = request.data.get("question")
    language = request.data.get("language", "fr")
    conversation_id = request.data.get("conversation_id")

    if not isinstance(question, str) or not question.strip():
        return Response(
            {"question": ["Ce champ est obligatoire."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(language, str) or not language.strip():
        return Response(
            {"language": ["Ce champ doit être une chaîne non vide."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if language.strip() not in {"fr", "darija", "ar"}:
        return Response(
            {"language": ["La langue doit être 'fr', 'darija' ou 'ar'."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            return Response(
                {"conversation_id": ["Cet identifiant doit être un entier."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if conversation_id < 1:
            return Response(
                {"conversation_id": ["Cet identifiant doit être positif."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    question = question.strip()
    language = language.strip()
    pipeline_result = run_rag_pipeline(question, language)
    answer = pipeline_result["answer"]
    sources = pipeline_result["sources"]
    metadata = get_response_metadata(pipeline_result["answer_mode"], sources)

    from conversations.models import Conversation, Message

    with transaction.atomic():
        if conversation_id is None:
            conversation = Conversation.objects.create(
                session_id=uuid.uuid4().hex,
                language=language,
            )
        else:
            conversation = Conversation.objects.filter(pk=conversation_id).first()
            if conversation is None:
                return Response(
                    {"conversation_id": ["Conversation introuvable."]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            conversation.language = language
            conversation.save(update_fields=["language", "updated_at"])

        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=question,
        )
        assistant_message = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=answer,
            sources=sources,
        )

    return Response(
        {
            "conversation_id": conversation.id,
            "assistant_message_id": assistant_message.id,
            "answer_mode": pipeline_result["answer_mode"],
            "question": question,
            "answer": answer,
            "language": language,
            "legal_warning": (
                ARABIC_LEGAL_WARNING
                if language == "ar"
                else DARJA_LEGAL_WARNING if language == "darija" else LEGAL_WARNING
            ),
            "sources": sources,
            "latency_ms": int((perf_counter() - started_at) * 1000),
            **metadata,
        }
    )

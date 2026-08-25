from rest_framework.decorators import api_view
from rest_framework.response import Response

from conversations.models import Conversation, Message
from feedback.models import Feedback
from knowledge.models import KnowledgeEntry, LegalCategory


@api_view(["GET"])
def stats(request):
    recent_questions = list(
        Message.objects.filter(role=Message.Role.USER)
        .order_by("-created_at", "-id")
        .values("id", "content", "created_at")[:5]
    )

    return Response(
        {
            "conversations_count": Conversation.objects.count(),
            "messages_count": Message.objects.count(),
            "assistant_messages_count": Message.objects.filter(
                role=Message.Role.ASSISTANT
            ).count(),
            "user_messages_count": Message.objects.filter(
                role=Message.Role.USER
            ).count(),
            "feedback_count": Feedback.objects.count(),
            "positive_feedback_count": Feedback.objects.filter(
                rating=Feedback.Rating.POSITIVE
            ).count(),
            "negative_feedback_count": Feedback.objects.filter(
                rating=Feedback.Rating.NEGATIVE
            ).count(),
            "knowledge_entries_count": KnowledgeEntry.objects.count(),
            "categories_count": LegalCategory.objects.count(),
            "recent_questions": recent_questions,
        }
    )

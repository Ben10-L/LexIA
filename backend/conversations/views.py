from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Conversation
from .serializers import ConversationSerializer


class ConversationListView(ListAPIView):
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.prefetch_related("messages").order_by("-updated_at")


class ConversationDetailView(RetrieveAPIView):
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.prefetch_related("messages")

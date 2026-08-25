from rest_framework.generics import ListCreateAPIView

from .models import Feedback
from .serializers import FeedbackSerializer


class FeedbackListCreateView(ListCreateAPIView):
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.select_related("message").order_by("-created_at")

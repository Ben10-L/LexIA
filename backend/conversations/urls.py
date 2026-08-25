from django.urls import path

from .views import ConversationDetailView, ConversationListView

app_name = "conversations"

urlpatterns = [
    path("", ConversationListView.as_view(), name="list"),
    path("<int:pk>/", ConversationDetailView.as_view(), name="detail"),
]

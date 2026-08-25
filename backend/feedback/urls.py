from django.urls import path

from .views import FeedbackListCreateView

app_name = "feedback"

urlpatterns = [
    path("", FeedbackListCreateView.as_view(), name="list-create"),
]

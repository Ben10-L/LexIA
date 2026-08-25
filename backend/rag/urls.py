from django.urls import path

from .views import chat
from .stats import stats
from .health import health

app_name = "rag"

urlpatterns = [
    path("chat/", chat, name="chat"),
    path("stats/", stats, name="stats"),
    path("health/", health, name="health"),
]

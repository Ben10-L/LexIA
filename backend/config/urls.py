"""Root URL configuration for LexIA."""
from django.contrib import admin
from django.urls import include, path

from rag.views import home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/conversations/", include("conversations.urls")),
    path("api/feedback/", include("feedback.urls")),
    path("api/", include("rag.urls")),
]

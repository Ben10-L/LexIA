from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "message__content")
    readonly_fields = ("created_at",)

from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "session_id", "language", "created_at", "updated_at")
    search_fields = ("session_id",)
    list_filter = ("language",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    search_fields = ("content", "conversation__session_id")
    list_filter = ("role",)
    readonly_fields = ("created_at",)

from django.contrib import admin

from .models import KnowledgeEntry, LegalCategory


@admin.register(LegalCategory)
class LegalCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "document_title",
        "article_number",
        "category",
        "language",
        "is_active",
        "updated_at",
    )
    list_filter = ("category", "language", "is_active")
    search_fields = ("document_title", "article_number", "content")
    readonly_fields = ("created_at", "updated_at")


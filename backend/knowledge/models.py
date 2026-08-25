from django.db import models


class LegalCategory(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "legal categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class KnowledgeEntry(models.Model):
    category = models.ForeignKey(
        LegalCategory,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    document_title = models.CharField(max_length=255)
    source_file = models.CharField(max_length=255, blank=True)
    book = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    chapter = models.CharField(max_length=255, blank=True)
    section = models.CharField(max_length=255, blank=True)
    article_number = models.CharField(max_length=100, blank=True)
    content = models.TextField()
    page_start = models.PositiveIntegerField(null=True, blank=True)
    page_end = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=10, default="fr")
    embedding_id = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document_title", "article_number", "id"]

    def __str__(self):
        reference = self.article_number or str(self.pk or "new")
        return f"{self.document_title} - {reference}"


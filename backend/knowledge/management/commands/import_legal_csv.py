import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from knowledge.models import KnowledgeEntry, LegalCategory


class Command(BaseCommand):
    help = "Import legal knowledge entries from a UTF-8 CSV file."

    COLUMN_ALIASES = {
        "article_number": (
            "article_number",
            "Article",
            "article",
            "Numéro article",
            "numero_article",
            "numero",
            "N°",
        ),
        "content": (
            "content",
            "Contenu",
            "contenu",
            "Texte",
            "texte",
            "legal_content",
            "Article_Text",
            "text",
            "body",
        ),
        "book": ("book", "Book", "Livre", "livre"),
        "title": ("title", "Title", "Titre", "titre"),
        "chapter": ("chapter", "Chapter", "Chapitre", "chapitre"),
        "section": ("section", "Section"),
        "page_start": ("page_start", "Page", "page", "Pages", "pages"),
        "page_end": ("page_end", "Page fin", "page_fin"),
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)
        parser.add_argument("--category", required=True)
        parser.add_argument("--document-title", required=True)

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        if not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        category_name = options["category"].strip()
        document_title = options["document_title"].strip()
        if not category_name or not document_title:
            raise CommandError("Category and document title cannot be empty.")

        category, _ = LegalCategory.objects.get_or_create(
            name=category_name,
            defaults={"slug": self._unique_slug(category_name)},
        )

        imported = 0
        skipped = 0
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                if not reader.fieldnames:
                    raise CommandError("The CSV file has no header row.")

                detected_columns = self._detect_columns(reader.fieldnames)
                self.stdout.write(
                    f"Detected CSV columns: {', '.join(reader.fieldnames)}"
                )
                if "content" not in detected_columns:
                    aliases = ", ".join(self.COLUMN_ALIASES["content"])
                    raise CommandError(
                        f"No legal content column detected. Expected one of: {aliases}"
                    )

                for row_number, row in enumerate(reader, start=2):
                    content = self._value(row, detected_columns, "content")
                    if not content:
                        skipped += 1
                        self.stderr.write(
                            self.style.WARNING(
                                f"Skipped row {row_number}: content is empty."
                            )
                        )
                        continue

                    article_number = self._value(
                        row, detected_columns, "article_number"
                    )
                    if KnowledgeEntry.objects.filter(
                        document_title=document_title,
                        article_number=article_number,
                        content=content,
                    ).exists():
                        skipped += 1
                        continue

                    KnowledgeEntry.objects.create(
                        category=category,
                        document_title=document_title,
                        source_file=(row.get("source_file") or csv_path.name).strip(),
                        book=self._value(row, detected_columns, "book"),
                        title=self._value(row, detected_columns, "title"),
                        chapter=self._value(row, detected_columns, "chapter"),
                        section=self._value(row, detected_columns, "section"),
                        article_number=article_number,
                        content=content,
                        page_start=self._optional_page_number(
                            self._value(row, detected_columns, "page_start"),
                            row_number,
                            "page_start",
                        ),
                        page_end=self._optional_page_number(
                            self._value(row, detected_columns, "page_end"),
                            row_number,
                            "page_end",
                        ),
                        language=(row.get("language") or "fr").strip(),
                        embedding_id=(row.get("embedding_id") or "").strip(),
                        is_active=self._boolean(row.get("is_active"), row_number),
                    )
                    imported += 1
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f"Could not read CSV file: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {imported} knowledge entries; skipped {skipped}."
            )
        )

    @classmethod
    def _detect_columns(cls, fieldnames):
        available = set(fieldnames)
        return {
            field: next((alias for alias in aliases if alias in available), None)
            for field, aliases in cls.COLUMN_ALIASES.items()
            if any(alias in available for alias in aliases)
        }

    @staticmethod
    def _value(row, detected_columns, field):
        column = detected_columns.get(field)
        return (row.get(column) or "").strip() if column else ""

    @staticmethod
    def _optional_page_number(value, row_number, field_name):
        value = (value or "").strip()
        if not value:
            return None

        match = re.search(r"\d+", value)
        if not match:
            raise CommandError(f"Invalid {field_name} on row {row_number}: {value!r}")
        number = int(match.group())
        if number < 0:
            raise CommandError(
                f"Invalid {field_name} on row {row_number}: must be positive."
            )
        return number

    @staticmethod
    def _boolean(value, row_number):
        value = (value or "true").strip().lower()
        if value in {"1", "true", "yes", "oui"}:
            return True
        if value in {"0", "false", "no", "non"}:
            return False
        raise CommandError(f"Invalid is_active value on row {row_number}: {value!r}")

    @staticmethod
    def _unique_slug(name):
        base_slug = slugify(name) or "category"
        slug = base_slug
        suffix = 2
        while LegalCategory.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug

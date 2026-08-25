import math
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from knowledge.models import KnowledgeEntry, LegalCategory


class Command(BaseCommand):
    help = "Preview or import Arabic legal TXT files from a folder."

    ARTICLE_PATTERN = re.compile(
        r"(?im)^[ \t]*(?P<label>المادة|الفصل|Article)[ \t]+"
        r"(?P<number>[0-9٠-٩]+|[A-Za-zÀ-ÿ]+|[\u0600-\u06FF]+)"
        r"(?:[ \t]*[:.\-–—])?"
    )
    CATEGORY_RULES = (
        (("الأسرة", "الاسرة"), "Droit de la famille"),
        (("الشغل",), "Droit du travail"),
        (("المسطرة الجنائية", "القانون الجنائي"), "Droit pénal et procédure pénale"),
        (("المسطرة المدنية",), "Procédure civile"),
        (("التحفيظ", "التعمير", "الكراء", "الحقوق العينية"), "Droit immobilier"),
        (("التوثيق", "المحاماة"), "Professions juridiques"),
        (("شركات", "شركة", "التجارة"), "Droit des affaires"),
        (("المستهلك",), "Protection du consommateur"),
        (("الجمارك",), "Droit douanier"),
        (("السير",), "Droit routier"),
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, type=Path)
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Write entries to the database. Without this flag, only preview.",
        )

    def handle(self, *args, **options):
        folder = Path(options["path"]).expanduser().resolve()
        confirm = options["confirm"]
        if not folder.is_dir():
            raise CommandError(f"TXT folder not found: {folder}")

        txt_files = sorted(folder.glob("*.txt"), key=lambda path: path.name)
        if not txt_files:
            raise CommandError(f"No TXT files found in: {folder}")

        mode = "IMPORT" if confirm else "DRY RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"{mode}: {folder}"))
        if not confirm:
            self.stdout.write("No database changes will be made. Use --confirm to import.")

        existing_keys = self._existing_entry_keys()
        planned_entries = []
        skipped = 0

        for txt_path in txt_files:
            text, encoding = self._read_text(txt_path)
            document_title = txt_path.stem.strip()
            category_name = self._infer_category(document_title)
            sections, strategy = self._split_text(text)
            file_created = 0
            file_skipped = 0

            for article_number, content in sections:
                content = content.strip()
                if not content:
                    file_skipped += 1
                    continue
                key = (
                    document_title,
                    article_number,
                    self._normalize_content(content),
                )
                if key in existing_keys:
                    file_skipped += 1
                    continue
                existing_keys.add(key)
                planned_entries.append(
                    {
                        "category_name": category_name,
                        "document_title": document_title,
                        "source_file": txt_path.name,
                        "article_number": article_number,
                        "content": content,
                    }
                )
                file_created += 1

            skipped += file_skipped
            self.stdout.write(
                f"- {txt_path.name}: encoding={encoding}, category={category_name}, "
                f"strategy={strategy}, new={file_created}, skipped={file_skipped}"
            )

        if confirm:
            self._create_entries(planned_entries)

        action = "Created" if confirm else "Would create"
        summary = (
            f"{action} {len(planned_entries)} knowledge entries from "
            f"{len(txt_files)} TXT files; skipped {skipped}."
        )
        self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _read_text(path):
        raw_content = path.read_bytes()
        errors = []
        for encoding in ("utf-8-sig", "utf-8", "cp1256"):
            try:
                return raw_content.decode(encoding), encoding
            except UnicodeDecodeError as exc:
                errors.append(f"{encoding}: {exc}")
        raise CommandError(
            f"Could not decode {path.name}. Tried utf-8-sig, utf-8 and cp1256. "
            + " | ".join(errors)
        )

    @classmethod
    def _split_text(cls, text):
        cleaned_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        matches = list(cls.ARTICLE_PATTERN.finditer(cleaned_text))
        if matches:
            sections = []
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned_text)
                content = cleaned_text[match.start() : end].strip()
                article_number = " ".join(
                    (match.group("label"), match.group("number"))
                )[:100]
                if content:
                    sections.append((article_number, content))
            if sections:
                return sections, "articles"
        return cls._split_into_word_chunks(cleaned_text), "word chunks"

    @staticmethod
    def _split_into_word_chunks(text):
        words = text.split()
        if not words:
            return []
        chunk_count = max(1, math.ceil(len(words) / 1500))
        chunk_size = math.ceil(len(words) / chunk_count)
        return [
            (f"Chunk {index + 1}", " ".join(words[start : start + chunk_size]))
            for index, start in enumerate(range(0, len(words), chunk_size))
        ]

    @classmethod
    def _infer_category(cls, filename):
        normalized_name = cls._normalize_content(filename)
        for keywords, category in cls.CATEGORY_RULES:
            if any(cls._normalize_content(keyword) in normalized_name for keyword in keywords):
                return category
        return "Droit marocain"

    @staticmethod
    def _normalize_content(content):
        normalized = unicodedata.normalize("NFKC", content).casefold()
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character) and character != "ـ"
        )
        return " ".join(normalized.split())

    @classmethod
    def _existing_entry_keys(cls):
        return {
            (
                document_title,
                article_number,
                cls._normalize_content(content),
            )
            for document_title, article_number, content in KnowledgeEntry.objects.values_list(
                "document_title", "article_number", "content"
            )
        }

    @classmethod
    @transaction.atomic
    def _create_entries(cls, entries):
        categories = {}
        for entry in entries:
            category_name = entry.pop("category_name")
            category = categories.get(category_name)
            if category is None:
                category, _ = LegalCategory.objects.get_or_create(
                    name=category_name,
                    defaults={"slug": cls._unique_slug(category_name)},
                )
                categories[category_name] = category
            KnowledgeEntry.objects.create(
                category=category,
                language="ar",
                **entry,
            )

    @staticmethod
    def _unique_slug(name):
        base_slug = slugify(name) or "legal-category"
        slug = base_slug
        suffix = 2
        while LegalCategory.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug

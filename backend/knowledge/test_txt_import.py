from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase

from knowledge.models import KnowledgeEntry, LegalCategory


class LegalTxtImportTests(TestCase):
    def test_dry_run_does_not_change_database(self):
        with TemporaryDirectory() as folder:
            Path(folder, "مدونة الشغل.txt").write_text(
                "المادة 1\nمقتضيات الشغل.\nالمادة 2\nمقتضيات أخرى.",
                encoding="utf-8",
            )
            output = StringIO()

            call_command("import_legal_txt_folder", path=folder, stdout=output)

        self.assertEqual(KnowledgeEntry.objects.count(), 0)
        self.assertEqual(LegalCategory.objects.count(), 0)
        self.assertIn("DRY RUN", output.getvalue())
        self.assertIn("Would create 2", output.getvalue())

    def test_confirm_imports_articles_and_skips_normalized_duplicates(self):
        with TemporaryDirectory() as folder:
            path = Path(folder, "مدونة الأسرة.txt")
            path.write_text(
                "المادة الأولى\nأحكام الأسرة.\nالمادة 2\nأحكام إضافية.",
                encoding="utf-8-sig",
            )

            call_command("import_legal_txt_folder", path=folder, confirm=True)
            call_command("import_legal_txt_folder", path=folder, confirm=True)

        self.assertEqual(KnowledgeEntry.objects.count(), 2)
        entry = KnowledgeEntry.objects.get(article_number="المادة الأولى")
        self.assertEqual(entry.document_title, "مدونة الأسرة")
        self.assertEqual(entry.language, "ar")
        self.assertEqual(entry.category.name, "Droit de la famille")

    def test_cp1256_and_word_chunk_fallback_are_supported(self):
        with TemporaryDirectory() as folder:
            text = " ".join(f"كلمة{i}" for i in range(2200))
            Path(folder, "نص قانوني.txt").write_bytes(text.encode("cp1256"))

            call_command("import_legal_txt_folder", path=folder, confirm=True)

        entries = list(KnowledgeEntry.objects.order_by("article_number"))
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(entry.article_number.startswith("Chunk ") for entry in entries))
        self.assertTrue(all(1000 <= len(entry.content.split()) <= 1500 for entry in entries))

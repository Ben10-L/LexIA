import csv
import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from .models import KnowledgeEntry, LegalCategory


class ImportLegalCsvTests(TestCase):
    def _write_csv(self, directory, fieldnames, rows):
        csv_path = Path(directory) / "legal.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return csv_path

    def test_imports_flexible_french_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = self._write_csv(
                directory,
                ["Livre", "Titre", "Chapitre", "Section", "Article", "Contenu", "Pages"],
                [
                    {
                        "Livre": "Livre premier",
                        "Titre": "Titre premier",
                        "Chapitre": "Chapitre premier",
                        "Section": "Section première",
                        "Article": "Article 1",
                        "Contenu": "Contenu juridique",
                        "Pages": "[5, 6, 7]",
                    }
                ],
            )

            stdout = io.StringIO()
            call_command(
                "import_legal_csv",
                csv_path,
                category="Fiscalité",
                document_title="Code Général des Impôts 2024",
                stdout=stdout,
            )

        category = LegalCategory.objects.get()
        entry = KnowledgeEntry.objects.get()
        self.assertEqual(category.name, "Fiscalité")
        self.assertEqual(entry.category, category)
        self.assertEqual(entry.document_title, "Code Général des Impôts 2024")
        self.assertEqual(entry.article_number, "Article 1")
        self.assertEqual(entry.source_file, "legal.csv")
        self.assertEqual(entry.book, "Livre premier")
        self.assertEqual(entry.title, "Titre premier")
        self.assertEqual(entry.chapter, "Chapitre premier")
        self.assertEqual(entry.section, "Section première")
        self.assertEqual(entry.page_start, 5)
        self.assertIn("Detected CSV columns:", stdout.getvalue())
        self.assertIn("Created 1 knowledge entries; skipped 0.", stdout.getvalue())

    def test_skips_empty_content_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = self._write_csv(
                directory,
                ["article", "texte"],
                [
                    {"article": "Article 1", "texte": "Même contenu"},
                    {"article": "Article 1", "texte": "Même contenu"},
                    {"article": "Article 2", "texte": ""},
                ],
            )

            stdout = io.StringIO()
            call_command(
                "import_legal_csv",
                csv_path,
                category="Fiscalité",
                document_title="Document test",
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(KnowledgeEntry.objects.count(), 1)
        self.assertIn("Created 1 knowledge entries; skipped 2.", stdout.getvalue())

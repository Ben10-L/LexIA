import csv
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase


class RagEvaluationTests(SimpleTestCase):
    def test_evaluation_csv_exists_with_at_least_120_questions(self):
        csv_path = Path(settings.BASE_DIR).parent / "data" / "evaluation_questions.csv"

        self.assertTrue(csv_path.exists())
        with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        self.assertGreaterEqual(len(rows), 120)
        self.assertEqual(
            set(rows[0]),
            {
                "question",
                "language",
                "expected_mode",
                "expected_domain",
                "expected_document_keyword",
                "expected_content_keywords",
                "forbidden_document_keywords",
                "forbidden_content_keywords",
                "should_have_sources",
                "notes",
            },
        )

    @patch("rag.management.commands.evaluate_rag.run_rag_pipeline")
    def test_evaluate_rag_command_runs_with_mocked_pipeline(self, pipeline):
        pipeline.return_value = {
            "answer": "Réponse de test",
            "sources": [],
            "answer_mode": "greeting",
        }
        output = StringIO()

        call_command("evaluate_rag", stdout=output)

        csv_path = Path(settings.BASE_DIR).parent / "data" / "evaluation_questions.csv"
        with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
            question_count = len(list(csv.DictReader(csv_file)))

        self.assertEqual(pipeline.call_count, question_count)
        self.assertIn("Evaluation summary", output.getvalue())
        self.assertIn(f"Total questions: {question_count}", output.getvalue())

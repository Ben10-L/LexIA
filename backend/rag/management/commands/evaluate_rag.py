import csv
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from rag.pipeline import run_rag_pipeline
from rag.pipeline import detect_text_language


class Command(BaseCommand):
    help = "Evaluate LexIA retrieval without calling an external LLM."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-failures",
            action="store_true",
            help="Show only failed questions in the main results table.",
        )
        parser.add_argument(
            "--domain",
            help="Evaluate only rows whose expected domain matches this value.",
        )
        parser.add_argument(
            "--mode",
            help="Evaluate only rows whose expected mode matches this value.",
        )

    def handle(self, *args, **options):
        csv_path = Path(settings.BASE_DIR).parent / "data" / "evaluation_questions.csv"
        if not csv_path.exists():
            raise CommandError(f"Evaluation CSV not found: {csv_path}")

        with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
        if not rows:
            raise CommandError("The evaluation CSV contains no questions.")

        rows = self.filter_rows(rows, options.get("domain"), options.get("mode"))
        if not rows:
            raise CommandError("No evaluation questions match the selected filters.")

        # Evaluation must be deterministic and must never spend LLM quota.
        with patch("rag.pipeline.is_llm_enabled", return_value=False):
            results = [self.evaluate_row(row) for row in rows]

        displayed = (
            [result for result in results if not result["final_pass"]]
            if options["only_failures"]
            else results
        )
        self.print_table(displayed)
        self.print_failures(results)
        self.print_summary(results)

    def evaluate_row(self, row):
        question = row["question"].strip()
        language = row.get("language", "fr").strip() or "fr"
        expected_mode = row["expected_mode"].strip()
        pipeline_result = run_rag_pipeline(
            question,
            language=language,
            retrieval_limit=5,
        )
        all_sources = pipeline_result.get("sources", [])
        top_sources = all_sources[:3]
        top_source = top_sources[0] if top_sources else {}

        accepted_modes = (
            {"llm", "structured"}
            if expected_mode in {"llm or structured", "llm_or_structured"}
            else {expected_mode}
        )
        mode_pass = pipeline_result.get("answer_mode") in accepted_modes
        should_have_sources = self.parse_source_expectation(
            row.get("should_have_sources"), expected_mode
        )
        source_presence_pass = bool(top_sources) == should_have_sources
        document_pass = self.any_source_matches(
            top_sources,
            "document_title",
            row.get("expected_document_keyword", ""),
        )
        content_pass = self.any_source_matches(
            top_sources,
            "excerpt",
            row.get("expected_content_keywords", ""),
        )
        forbidden_document_pass = not self.any_source_matches(
            top_sources,
            "document_title",
            row.get("forbidden_document_keywords", ""),
            empty_result=False,
        )
        forbidden_content_pass = not self.value_matches(
            top_source.get("excerpt", ""),
            row.get("forbidden_content_keywords", ""),
        )
        forbidden_pass = forbidden_document_pass and forbidden_content_pass
        answer = pipeline_result.get("answer", "")
        language_pass = self.language_is_consistent(answer, language)
        answer_quality_pass = self.answer_quality_is_sufficient(
            answer, pipeline_result.get("answer_mode", "")
        )
        final_pass = all(
            (
                mode_pass,
                source_presence_pass,
                document_pass,
                content_pass,
                forbidden_pass,
                language_pass,
                answer_quality_pass,
            )
        )
        failure_types = []
        if not mode_pass:
            failure_types.append("A. wrong mode")
        if not source_presence_pass:
            failure_types.append("B. no source" if should_have_sources else "B. unexpected source")
        if not document_pass:
            failure_types.append("C. wrong document")
        if not content_pass:
            failure_types.append("D. expected keyword missing")
        if not forbidden_document_pass:
            failure_types.append("E. forbidden document returned")
        if not forbidden_content_pass:
            failure_types.append("F. forbidden content returned")
        if not language_pass:
            failure_types.append("G. language inconsistency")
        if not answer_quality_pass:
            failure_types.append("H. answer too vague")

        return {
            "question": question,
            "expected_domain": row["expected_domain"].strip(),
            "expected_mode": expected_mode,
            "top_document": top_source.get("document_title", ""),
            "top_article": top_source.get("article_number", ""),
            "mode_pass": mode_pass,
            "source_presence_pass": source_presence_pass,
            "document_pass": document_pass,
            "content_pass": content_pass,
            "forbidden_pass": forbidden_pass,
            "language_pass": language_pass,
            "answer_quality_pass": answer_quality_pass,
            "final_pass": final_pass,
            "failure_types": failure_types,
            "sources": all_sources,
        }

    @staticmethod
    def filter_rows(rows, domain_filter, mode_filter):
        domain_aliases = {
            "fiscalite": "fiscal",
            "family": "famille",
            "labour": "travail",
            "criminal": "penal",
        }
        wanted_domain = (domain_filter or "").casefold().strip()
        wanted_domain = domain_aliases.get(wanted_domain, wanted_domain)
        wanted_mode = (mode_filter or "").casefold().strip()

        def matches(row):
            domain = row.get("expected_domain", "").casefold()
            mode = row.get("expected_mode", "").casefold()
            return (not wanted_domain or wanted_domain in domain) and (
                not wanted_mode or wanted_mode == mode
            )

        return [row for row in rows if matches(row)]

    @staticmethod
    def parse_source_expectation(value, expected_mode):
        normalized = (value or "").strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
        return expected_mode in {"structured", "llm", "llm or structured", "llm_or_structured"}

    @staticmethod
    def language_is_consistent(answer, language):
        detected = detect_text_language(answer)
        if language == "ar":
            return detected in {"ar", "unknown"}
        if language == "fr":
            return detected in {"latin", "unknown"}
        if language == "darija":
            return detected in {"latin", "unknown"}
        return True

    @staticmethod
    def answer_quality_is_sufficient(answer, answer_mode):
        if answer_mode == "structured":
            return len(answer.strip()) >= 120
        if answer_mode == "unclear_legal":
            return len(answer.strip()) >= 60 and any(mark in answer for mark in ("?", "؟"))
        return bool(answer.strip())

    @classmethod
    def any_source_matches(cls, sources, field, expectation, empty_result=True):
        if not expectation.strip():
            return empty_result
        return any(cls.value_matches(source.get(field, ""), expectation) for source in sources)

    @staticmethod
    def value_matches(actual_value, expectation):
        alternatives = [item.strip() for item in expectation.split("|") if item.strip()]
        if not alternatives:
            return False
        actual = str(actual_value).casefold()
        return any(alternative.casefold() in actual for alternative in alternatives)

    def print_table(self, results):
        columns = [
            ("Question", "question", 34),
            ("Domain", "expected_domain", 18),
            ("Top document", "top_document", 24),
            ("Top article", "top_article", 18),
            ("Doc", "document_pass", 5),
            ("Content", "content_pass", 7),
            ("Forbidden", "forbidden_pass", 9),
            ("Lang", "language_pass", 5),
            ("Quality", "answer_quality_pass", 7),
            ("Final", "final_pass", 5),
        ]

        def format_value(value, width):
            text = "PASS" if value is True else "FAIL" if value is False else str(value)
            if len(text) > width:
                text = text[: width - 1] + "…"
            return text.ljust(width)

        self.stdout.write(" | ".join(title.ljust(width) for title, _, width in columns))
        self.stdout.write("-+-".join("-" * width for _, _, width in columns))
        for result in results:
            self.stdout.write(
                " | ".join(format_value(result[key], width) for _, key, width in columns)
            )
        if not results:
            self.stdout.write("No failed questions.")

    def print_failures(self, results):
        failures = [result for result in results if not result["final_pass"]]
        if not failures:
            return
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Failure details (top 5 sources)"))
        for result in failures:
            self.stdout.write(f"\nQuestion: {result['question']}")
            for rank, source in enumerate(result["sources"][:5], start=1):
                excerpt = " ".join(source.get("excerpt", "").split())[:180]
                self.stdout.write(
                    f"  {rank}. {source.get('document_title', '')} | "
                    f"{source.get('article_number', '')} | "
                    f"{source.get('category', '')} | {excerpt}"
                )
            if not result["sources"]:
                self.stdout.write("  No sources retrieved.")
            self.stdout.write(f"  Failure types: {', '.join(result['failure_types'])}")

    def print_summary(self, results):
        total = len(results)
        passed = sum(result["final_pass"] for result in results)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Evaluation summary"))
        self.stdout.write(f"Total questions: {total}")
        self.stdout.write(f"Passed: {passed}/{total}")
        self.stdout.write(f"Failed: {total - passed}/{total}")
        self.stdout.write(f"Retrieval score: {passed / total * 100:.1f}%")
        for mode_name in ("unclear_legal", "off_topic"):
            mode_results = [
                result for result in results if result["expected_mode"] == mode_name
            ]
            if mode_results:
                mode_passed = sum(result["final_pass"] for result in mode_results)
                self.stdout.write(
                    f"{mode_name} score: {mode_passed}/{len(mode_results)} "
                    f"({mode_passed / len(mode_results) * 100:.1f}%)"
                )
        language_passed = sum(result["language_pass"] for result in results)
        self.stdout.write(
            f"Language consistency score: {language_passed}/{total} "
            f"({language_passed / total * 100:.1f}%)"
        )
        failures = [result for result in results if not result["final_pass"]]
        by_domain = Counter(result["expected_domain"] for result in failures)
        by_type = Counter(
            failure_type
            for result in failures
            for failure_type in result["failure_types"]
        )
        self.stdout.write("Failures by domain: " + (", ".join(f"{key}={value}" for key, value in sorted(by_domain.items())) or "none"))
        self.stdout.write("Failures by type: " + (", ".join(f"{key}={value}" for key, value in sorted(by_type.items())) or "none"))

import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from conversations.models import Message
from knowledge.models import KnowledgeEntry, LegalCategory

from .intent import (
    ARABIC_GREETING_ANSWER,
    ARABIC_OFF_TOPIC_ANSWER,
    ARABIC_OUT_OF_SCOPE_ANSWER,
    ARABIC_THANKS_ANSWER,
    DARJA_GREETING_ANSWER,
    DARJA_OFF_TOPIC_ANSWER,
    DARJA_OUT_OF_SCOPE_ANSWER,
    DARJA_THANKS_ANSWER,
    GREETING_ANSWER,
    OFF_TOPIC_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    THANKS_ANSWER,
    get_unclear_legal_answer,
)
from .pipeline import FALLBACK_ANSWER
from .views import ARABIC_LEGAL_WARNING, LEGAL_WARNING


class ChatApiTests(APITestCase):
    def setUp(self):
        self.semantic_search = patch(
            "rag.hybrid_search.search_knowledge_semantic",
            return_value=[],
        )
        self.semantic_search.start()
        self.addCleanup(self.semantic_search.stop)
        self.llm = patch("rag.pipeline.is_llm_enabled", return_value=False)
        self.llm.start()
        self.addCleanup(self.llm.stop)

    def assert_saved_assistant_message(self, response):
        data = response.json()
        assistant_message = Message.objects.get(pk=data["assistant_message_id"])
        self.assertEqual(assistant_message.role, Message.Role.ASSISTANT)
        self.assertEqual(assistant_message.conversation_id, data["conversation_id"])
        self.assertEqual(assistant_message.content, data["answer"])

    def create_legal_entry(self, category, document_title, content):
        legal_category = LegalCategory.objects.create(
            name=category,
            slug=f"test-{LegalCategory.objects.count() + 1}",
        )
        return KnowledgeEntry.objects.create(
            category=legal_category,
            document_title=document_title,
            article_number="المادة 1",
            content=content,
        )

    def test_chat_returns_fallback_when_no_result_exists(self):
        response = self.client.post(
            "/api/chat/",
            {"question": "Question fiscale introuvable", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data.pop("conversation_id"), int)
        assistant_message_id = data.pop("assistant_message_id")
        self.assertIsInstance(data.pop("latency_ms"), int)
        self.assertEqual(
            Message.objects.get(pk=assistant_message_id).role,
            Message.Role.ASSISTANT,
        )
        self.assertEqual(
            data,
            {
                "question": "Question fiscale introuvable",
                "answer": FALLBACK_ANSWER,
                "language": "fr",
                "legal_warning": LEGAL_WARNING,
                "sources": [],
                "answer_mode": "fallback",
                "confidence": "low",
                "retrieval_method": "none",
            },
        )

    def test_chat_rejects_an_empty_question(self):
        response = self.client.post(
            "/api/chat/", {"question": "", "language": "fr"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_vague_arabic_tax_questions_request_clarification(self, hybrid_search):
        for question in ("نسبة الضريبة؟", "ثمن الضرائب؟", "شحال الضريبة؟"):
            with self.subTest(question=question):
                response = self.client.post(
                    "/api/chat/",
                    {"question": question, "language": "ar"},
                    format="json",
                )
                data = response.json()
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(data["answer_mode"], "unclear_legal")
                self.assertEqual(
                    data["answer"], get_unclear_legal_answer("fiscal", "ar")
                )
                self.assertEqual(data["sources"], [])
                self.assertEqual(data["confidence"], "none")
                self.assertEqual(data["retrieval_method"], "none")
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_broad_corporate_tax_question_requests_clarification(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "الضريبة على الشركات", "language": "ar"},
            format="json",
        )

        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data["answer_mode"], "unclear_legal")
        self.assertEqual(data["sources"], [])
        self.assertIn("الضريبة على الشركات", data["answer"])
        self.assertIn("نسبة الضريبة", data["answer"])
        self.assertEqual(data["confidence"], "none")
        self.assertEqual(data["retrieval_method"], "none")
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_vague_general_legal_question_requests_clarification(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "عندي مشكل قانوني", "language": "ar"},
            format="json",
        )

        self.assertEqual(response.json()["answer_mode"], "unclear_legal")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_vague_tax_question_is_localized_in_french_and_darija(self, hybrid_search):
        cases = (
            ("taux d’impôt ?", "fr"),
            ("ch7al dariba?", "darija"),
        )
        for question, language in cases:
            with self.subTest(language=language):
                response = self.client.post(
                    "/api/chat/",
                    {"question": question, "language": language},
                    format="json",
                )
                data = response.json()
                self.assertEqual(data["answer_mode"], "unclear_legal")
                self.assertEqual(data["answer"], get_unclear_legal_answer("fiscal", language))
                self.assertEqual(data["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_darija_greeting_returns_localized_answer(self, hybrid_search):
        response = self.client.post(
            "/api/chat/", {"question": "salam", "language": "darija"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], DARJA_GREETING_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "greeting")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_darija_thanks_returns_localized_answer(self, hybrid_search):
        response = self.client.post(
            "/api/chat/", {"question": "chokran", "language": "darija"}, format="json"
        )

        self.assertEqual(response.json()["answer"], DARJA_THANKS_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "thanks")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_darija_general_question_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "chno ahsan telephone", "language": "darija"},
            format="json",
        )

        self.assertEqual(response.json()["answer"], DARJA_OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "off_topic")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_arabic_script_darija_phone_question_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "شنو أحسن هاتف؟", "language": "darija"},
            format="json",
        )

        self.assertEqual(response.json()["answer_mode"], "off_topic")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    def test_darija_divorce_question_is_in_scope(self):
        arabic_legal_text = (
            "تنظم مدونة الأسرة أحكام الطلاق والزواج والنفقة والحضانة."
        )
        self.create_legal_entry(
            "Droit de la famille",
            "مدونة الأسرة",
            arabic_legal_text,
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "kifach ndir tla9", "language": "darija"},
            format="json",
        )

        data = response.json()
        self.assertEqual(data["answer_mode"], "structured")
        self.assertTrue(data["sources"])
        self.assertIn("7sab lmasadir", data["answer"])
        self.assertIn("B tariqa bsita", data["answer"])
        self.assertNotIn(arabic_legal_text, data["answer"])
        self.assertIn(arabic_legal_text, data["sources"][0]["excerpt"])

    def test_darija_legal_questions_return_sources(self):
        category = LegalCategory.objects.create(name="Darija", slug="darija-tests")
        entries = [
            ("Code Général des Impôts 2024", "Article 10", "Charges déductibles", "Les charges déductibles du résultat fiscal."),
            ("Loi n°17-95 relative aux sociétés anonymes", "Article Premier", "Constitution", "La constitution d'une société anonyme."),
            ("Instruction Générale des Opérations de Change 2024", "Article 7", "Virement international", "Virement à destination de l'étranger."),
        ]
        for document, article, title, content in entries:
            KnowledgeEntry.objects.create(
                category=category,
                document_title=document,
                article_number=article,
                title=title,
                content=content,
            )

        for question in (
            "chno homa les charges déductibles?",
            "kifach ncréyi société anonyme?",
            "kifach ndir virement lbarra?",
        ):
            with self.subTest(question=question):
                response = self.client.post(
                    "/api/chat/", {"question": question, "language": "darija"}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue(response.json()["sources"])
                self.assertEqual(response.json()["answer_mode"], "structured")

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_arabic_greeting_returns_localized_answer(self, hybrid_search):
        response = self.client.post(
            "/api/chat/", {"question": "السلام عليكم", "language": "ar"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], ARABIC_GREETING_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "greeting")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_arabic_thanks_returns_localized_answer(self, hybrid_search):
        response = self.client.post(
            "/api/chat/", {"question": "شكرا", "language": "ar"}, format="json"
        )

        self.assertEqual(response.json()["answer"], ARABIC_THANKS_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "thanks")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_arabic_general_question_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/", {"question": "ما هو أفضل هاتف؟", "language": "ar"}, format="json"
        )

        self.assertEqual(response.json()["answer"], ARABIC_OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["answer_mode"], "off_topic")
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    def test_arabic_divorce_question_is_in_scope(self):
        self.create_legal_entry(
            "Droit de la famille",
            "مدونة الأسرة",
            "تنظم مدونة الأسرة أحكام الطلاق والزواج والنفقة والحضانة.",
        )
        response = self.client.post(
            "/api/chat/", {"question": "كيف أطلب الطلاق؟", "language": "ar"}, format="json"
        )

        data = response.json()
        self.assertEqual(data["answer_mode"], "structured")
        self.assertTrue(data["sources"])
        self.assertIn("بشكل مبسط", data["answer"])
        self.assertIn("مدونة الأسرة", data["answer"])
        self.assertIn("المادة 1", data["answer"])
        self.assertNotIn("مقتطف:", data["answer"])
        self.assertEqual(data["legal_warning"], ARABIC_LEGAL_WARNING)
        self.assertNotIn(data["legal_warning"], data["answer"])

    def test_arabic_legal_questions_return_sources(self):
        category = LegalCategory.objects.create(name="Arabic", slug="arabic-tests")
        entries = [
            ("Code Général des Impôts 2024", "Article 10", "Charges déductibles", "Les charges déductibles du résultat fiscal."),
            ("Loi n°17-95 relative aux sociétés anonymes", "Article Premier", "Constitution", "La constitution d'une société anonyme."),
            ("Instruction Générale des Opérations de Change 2024", "Article 7", "Virement international", "Virement à destination de l'étranger."),
        ]
        for document, article, title, content in entries:
            KnowledgeEntry.objects.create(
                category=category,
                document_title=document,
                article_number=article,
                title=title,
                content=content,
            )

        for question in (
            "ما هي المصاريف القابلة للخصم؟",
            "كيف يمكن تأسيس شركة مساهمة؟",
            "كيف يتم التحويل إلى الخارج؟",
        ):
            with self.subTest(question=question):
                response = self.client.post(
                    "/api/chat/", {"question": question, "language": "ar"}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue(response.json()["sources"])
                self.assertEqual(response.json()["answer_mode"], "structured")

    def test_arabic_structured_answer_does_not_dump_french_source_text(self):
        category = LegalCategory.objects.create(
            name="Fiscalité Arabic response",
            slug="fiscalite-arabic-response",
        )
        french_legal_text = (
            "Les charges déductibles au sens de l'article 10 comprennent les "
            "charges d'exploitation engagées ou supportées pour les besoins "
            "de l'activité imposable de la société."
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10.- Charges déductibles",
            title="Charges déductibles",
            content=french_legal_text,
            page_start=31,
        )

        response = self.client.post(
            "/api/chat/",
            {"question": "ما هي المصاريف القابلة للخصم؟", "language": "ar"},
            format="json",
        )

        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data["answer_mode"], "structured")
        self.assertIn("حسب المصادر", data["answer"])
        self.assertIn("بشكل مبسط", data["answer"])
        self.assertIn("المصاريف القابلة للخصم", data["answer"])
        self.assertIn("الربح الخاضع للضريبة", data["answer"])
        self.assertIn("نشاط المقاولة", data["answer"])
        self.assertGreaterEqual(data["answer"].count("- "), 2)
        self.assertNotIn("Les charges déductibles au sens", data["answer"])
        self.assertTrue(data["sources"])
        self.assertIn(french_legal_text[:100], data["sources"][0]["excerpt"])
        self.assertEqual(data["legal_warning"], ARABIC_LEGAL_WARNING)
        self.assertNotIn(data["legal_warning"], data["answer"])

    def test_arabic_foreign_transfer_ranks_igoc_article_7_or_8(self):
        category = LegalCategory.objects.create(name="Change Arabic", slug="change-ar")
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Instruction Générale des Opérations de Change 2024",
            article_number=(
                "Article 7 - Règlements au profit de non-résidents ou à "
                "destination de l’étranger"
            ),
            title="Principes de base",
            content=(
                "Les règlements au profit de non-résidents ou à destination de "
                "l’étranger peuvent être effectués par virement à destination "
                "de l’étranger."
            ),
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Instruction Générale des Opérations de Change 2024",
            article_number=(
                "Article 8 - Règlements au profit de résidents ou en provenance "
                "de l’étranger"
            ),
            title="Principes de base",
            content="Les règlements en provenance de l’étranger sont autorisés.",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Autre document de change",
            article_number="Article 90 - Transports internationaux",
            title="Transport",
            content="Dispositions générales relatives aux opérations internationales.",
        )

        response = self.client.post(
            "/api/chat/",
            {"question": "كيف يتم التحويل إلى الخارج؟", "language": "ar"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(response.json()["answer_mode"], {"structured", "llm"})
        self.assertTrue(response.json()["sources"])
        self.assertIn(
            "Instruction Générale des Opérations de Change 2024",
            response.json()["sources"][0]["document_title"],
        )
        self.assertTrue(
            any(
                "Article 7" in source["article_number"]
                or "Article 8" in source["article_number"]
                for source in response.json()["sources"]
            )
        )

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_greeting_returns_friendly_answer_without_sources(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "bonjour", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], GREETING_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(response.json()["answer_mode"], "greeting")
        self.assertEqual(response.json()["confidence"], "none")
        self.assertEqual(response.json()["retrieval_method"], "none")
        self.assertIsInstance(response.json()["latency_ms"], int)
        self.assert_saved_assistant_message(response)
        hybrid_search.assert_not_called()
        messages = Message.objects.filter(
            conversation_id=response.json()["conversation_id"]
        ).order_by("created_at", "id")
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages[0].content, "bonjour")
        self.assertEqual(messages[1].content, GREETING_ANSWER)

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_thanks_returns_friendly_answer_without_sources(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "merci", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], THANKS_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(response.json()["answer_mode"], "thanks")
        self.assert_saved_assistant_message(response)
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_off_topic_question_returns_no_sources(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "quel est le meilleur téléphone ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(response.json()["answer_mode"], "off_topic")
        self.assert_saved_assistant_message(response)
        hybrid_search.assert_not_called()
        messages = Message.objects.filter(
            conversation_id=response.json()["conversation_id"]
        ).order_by("created_at", "id")
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages[0].role, Message.Role.USER)
        self.assertEqual(messages[1].role, Message.Role.ASSISTANT)

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_age_question_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "quelle age a tu?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_identity_question_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "qui es-tu ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_joke_request_is_off_topic(self, hybrid_search):
        response = self.client.post(
            "/api/chat/",
            {"question": "raconte une blague", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer"], OFF_TOPIC_ANSWER)
        self.assertEqual(response.json()["sources"], [])
        hybrid_search.assert_not_called()

    def test_divorce_question_is_in_scope(self):
        arabic_legal_text = (
            "تنظم مدونة الأسرة أحكام الطلاق والزواج والنفقة والحضانة."
        )
        self.create_legal_entry(
            "Droit de la famille",
            "مدونة الأسرة",
            arabic_legal_text,
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "Comment divorcer au Maroc ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["answer_mode"], "structured")
        self.assertTrue(data["sources"])
        self.assertIn("Selon les sources", data["answer"])
        self.assertIn("En termes simples", data["answer"])
        self.assertIn("مدونة الأسرة", data["answer"])
        self.assertNotIn(arabic_legal_text, data["answer"])
        self.assertIn(arabic_legal_text, data["sources"][0]["excerpt"])
        self.assertNotIn(data["legal_warning"], data["answer"])
        self.assert_saved_assistant_message(response)

    def test_dismissal_question_is_in_scope(self):
        self.create_legal_entry(
            "Droit du travail",
            "مدونة الشغل",
            "تنظم مدونة الشغل عقد العمل والفصل من العمل وحقوق الأجير.",
        )
        response = self.client.post(
            "/api/chat/",
            {
                "question": "Quels sont mes droits en cas de licenciement ?",
                "language": "fr",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer_mode"], "structured")
        self.assertTrue(response.json()["sources"])
        self.assert_saved_assistant_message(response)

    def test_complaint_question_is_in_scope(self):
        self.create_legal_entry(
            "Droit pénal et procédure pénale",
            "قانون المسطرة الجنائية",
            "تنظم المسطرة الجنائية تقديم شكاية إلى النيابة العامة.",
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "Comment déposer une plainte ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["answer_mode"], "structured")
        self.assertTrue(response.json()["sources"])
        self.assert_saved_assistant_message(response)

    def test_theft_sanction_question_is_in_scope(self):
        self.create_legal_entry(
            "Droit pénal et procédure pénale",
            "مجموعة القانون الجنائي",
            "يبين القانون الجنائي عقوبة جريمة السرقة.",
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "شنو عقوبة السرقة؟", "language": "darija"},
            format="json",
        )

        self.assertEqual(response.json()["answer_mode"], "structured")
        self.assertTrue(response.json()["sources"])

    def test_rent_problem_question_is_in_scope(self):
        self.create_legal_entry(
            "Droit immobilier",
            "قانون الكراء والتحفيظ العقاري",
            "تنظم هذه الأحكام الكراء والبail والحقوق المرتبطة بالعقار.",
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "عندي مشكل فالكراء", "language": "darija"},
            format="json",
        )

        self.assertEqual(response.json()["answer_mode"], "structured")
        self.assertTrue(response.json()["sources"])

    def test_consumer_rights_question_is_in_scope(self):
        self.create_legal_entry(
            "Protection du consommateur",
            "قانون حماية المستهلك",
            "يحدد قانون حماية المستهلك حقوق المستهلك وضمان المنتوج المعيب.",
        )
        response = self.client.post(
            "/api/chat/",
            {"question": "ما هي حقوق المستهلك؟", "language": "ar"},
            format="json",
        )

        data = response.json()
        self.assertEqual(data["answer_mode"], "structured")
        self.assertTrue(data["sources"])
        self.assertIn("بشكل مبسط", data["answer"])
        self.assertIn("حماية المستهلك", data["answer"])
        self.assertIn("المادة 1", data["answer"])

    def test_charges_deductibles_question_still_returns_sources(self):
        category = LegalCategory.objects.create(
            name="Fiscalité charges",
            slug="fiscalite-charges",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10.- Charges déductibles",
            title="Charges déductibles",
            content="Les charges déductibles du résultat fiscal sont définies ici.",
            page_start=31,
        )

        response = self.client.post(
            "/api/chat/",
            {"question": "Quelles sont les charges déductibles ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["sources"])
        self.assertEqual(response.json()["answer_mode"], "structured")
        self.assertEqual(response.json()["confidence"], "medium")
        self.assertEqual(response.json()["retrieval_method"], "hybrid")
        self.assert_saved_assistant_message(response)
        self.assertEqual(
            response.json()["sources"][0]["article_number"],
            "Article 10.- Charges déductibles",
        )

    def test_chat_returns_sources_for_matching_entry(self):
        category = LegalCategory.objects.create(
            name="Fiscalité",
            slug="fiscalite",
        )
        content = "Imposition des sociétés marocaines. " + ("x" * 450)
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 2",
            title="Impôt sur les sociétés",
            content=content,
            page_start=5,
            page_end=7,
        )

        response = self.client.post(
            "/api/chat/",
            {"question": "Quelle imposition pour les sociétés ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data["assistant_message_id"], int)
        self.assertIn("Article 2", data["answer"])
        self.assertIn("Code Général des Impôts 2024", data["answer"])
        self.assertIn("En termes simples", data["answer"])
        self.assertLess(len(data["answer"]), len(content) + 300)
        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(
            data["sources"][0],
            {
                "document_title": "Code Général des Impôts 2024",
                "article_number": "Article 2",
                "category": "Fiscalité",
                "page_start": 5,
                "page_end": 7,
                "excerpt": content[:400],
            },
        )
        self.assertEqual(len(data["sources"][0]["excerpt"]), 400)

    @patch("rag.views.run_rag_pipeline")
    def test_llm_answer_returns_high_confidence_metadata(self, pipeline):
        pipeline.return_value = {
            "answer": "Réponse Gemini fondée sur LexIA.",
            "sources": [
                {
                    "document_title": "Code Général des Impôts 2024",
                    "article_number": "Article 10",
                    "category": "Fiscalité",
                    "page_start": 31,
                    "page_end": None,
                    "excerpt": "Les charges déductibles...",
                }
            ],
            "answer_mode": "llm",
        }

        response = self.client.post(
            "/api/chat/",
            {"question": "Quelles sont les charges déductibles ?", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["confidence"], "high")
        self.assertEqual(response.json()["retrieval_method"], "hybrid")
        self.assertIsInstance(response.json()["latency_ms"], int)

    def test_payment_abroad_question_still_returns_sources(self):
        category = LegalCategory.objects.create(name="Change", slug="change-test")
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Instruction Générale des Opérations de Change 2024",
            article_number="Article 8",
            title="Paiement vers l’étranger",
            content="Les paiements vers l’étranger sont réalisés selon ces règles.",
        )

        response = self.client.post(
            "/api/chat/",
            {
                "question": "Comment fonctionne un paiement vers l’étranger ?",
                "language": "fr",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["sources"])
        self.assertEqual(response.json()["answer_mode"], "structured")

    def test_societe_anonyme_question_still_returns_sources(self):
        category = LegalCategory.objects.create(
            name="Sociétés",
            slug="societes-test",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Loi n°17-95 relative aux sociétés anonymes",
            article_number="Article Premier",
            title="Constitution d’une société anonyme",
            content="La société anonyme est constituée selon les présentes règles.",
        )

        response = self.client.post(
            "/api/chat/",
            {
                "question": "Comment créer une société anonyme ?",
                "language": "fr",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["sources"])
        self.assertEqual(response.json()["answer_mode"], "structured")


class SemanticSearchTests(SimpleTestCase):
    @patch("rag.semantic_search.get_collection", side_effect=RuntimeError("Unavailable"))
    def test_returns_empty_list_when_chroma_is_unavailable(self, get_collection):
        from .semantic_search import search_knowledge_semantic

        self.assertEqual(search_knowledge_semantic("Question juridique"), [])


class HybridSearchTests(TestCase):
    def setUp(self):
        self.category = LegalCategory.objects.create(
            name="Fiscalité",
            slug="fiscalite-hybrid",
        )

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_prefers_article_and_title_matches_over_weak_semantic_result(
        self, semantic_search
    ):
        weak_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 268",
            title="Liquidation",
            content="Dispositions relatives à la liquidation.",
        )
        strong_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10",
            title="Charges déductibles",
            content="Les charges déductibles sont admises selon les règles fiscales.",
        )
        semantic_search.return_value = [weak_result]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("Article 10 charges déductibles")

        self.assertEqual(results[0], strong_result)

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_fiscal_synonyms_rank_charges_deductibles_first(self, semantic_search):
        weak_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 268",
            title="Liquidation",
            content="Liquidation de l'impôt dû par une société.",
        )
        expected_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10.- Charges déductibles",
            title="Charges déductibles",
            content="Les charges sont déductibles du résultat fiscal de la société.",
        )
        semantic_search.return_value = [weak_result]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid(
            "Quels frais une entreprise peut retirer de son bénéfice imposable ?"
        )

        self.assertEqual(results[0], expected_result)

    @patch("rag.hybrid_search.search_knowledge_semantic", return_value=[])
    def test_shareholder_query_prefers_shareholder_assembly_article(
        self, semantic_search
    ):
        weak_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 118.- Règles comptables",
            content="Règles relatives aux obligations comptables.",
        )
        expected_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Loi n°17-95 relative aux sociétés anonymes",
            article_number="Article 107",
            section="Assemblées d'actionnaires",
            content="Les assemblées d'actionnaires sont générales ou spéciales.",
        )

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid(
            "Quelles sont les règles relatives aux actionnaires ?"
        )

        self.assertEqual(results[0], expected_result)
        self.assertNotEqual(results[0], weak_result)

    @patch("rag.hybrid_search.search_knowledge_semantic", return_value=[])
    def test_international_transfer_query_prefers_foreign_payment_article(
        self, semantic_search
    ):
        weak_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Instruction Générale des Opérations de Change 2024",
            article_number="Article 86.- Transport international",
            content="Règlements dans le cadre du transport international.",
        )
        expected_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Instruction Générale des Opérations de Change 2024",
            article_number="Article 7.- Règlements à destination de l’étranger",
            content="Le paiement peut être effectué par virement à destination de l’étranger.",
        )

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid(
            "Quelles sont les règles pour un virement international ?"
        )

        self.assertEqual(results[0], expected_result)
        self.assertNotEqual(results[0], weak_result)

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_dismissal_query_penalizes_transitional_article(self, semantic_search):
        transitional = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة الشغل",
            article_number="المادة 589",
            content=(
                "يسري مفعول هذا القانون بعد ستة أشهر من تاريخ نشره في "
                "الجريدة الرسمية."
            ),
        )
        substantive = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة الشغل",
            article_number="المادة 43",
            content=(
                "يكون إنهاء عقد الشغل مبنيا على احترام أجل الإخطار ما لم "
                "يصدر خطأ جسيم."
            ),
        )
        semantic_search.return_value = [transitional]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("طردوني من الخدمة شنو ندير؟")

        self.assertEqual(results[0], substantive)
        self.assertNotEqual(results[0], transitional)

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_theft_query_prefers_substantive_penal_code_article(self, semantic_search):
        generic_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مجموعة القانون الجنائي",
            article_number="الفصل 125",
            content="الدفاع الشرعي ضد مرتكب السرقة من بين الحالات العامة.",
        )
        theft_results = [
            KnowledgeEntry.objects.create(
                category=self.category,
                document_title="مجموعة القانون الجنائي",
                article_number=article,
                content=content,
            )
            for article, content in (
                ("الفصل 506", "سرقة الأشياء الزهيدة يعاقب عليها بالحبس وغرامة."),
                ("الفصل 507", "يعاقب على السرقة بالسجن إذا اقترنت بظرف مشدد."),
                ("الفصل 510", "من سرق في هذه الحالة يعاقب بالسجن أو الحبس."),
            )
        ]
        semantic_search.return_value = [generic_result]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("شنو عقوبة السرقة؟")

        self.assertIn(results[0], theft_results)
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result.document_title, "مجموعة القانون الجنائي")
            self.assertTrue(
                any(term in result.content for term in ("السرقة", "سرق", "اختلس"))
            )

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_rent_query_prefers_rent_document_over_urbanism(self, semantic_search):
        urbanism = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="قانون التعمير",
            article_number="المادة 20",
            content="قواعد البناء والتجزئة العقارية.",
        )
        rent_result = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="الكراء – استيفاء الوجيبة",
            article_number="المادة الثانية",
            content="يمكن للمكري طلب أداء وجيبة الكراء المستحقة من المكتري.",
        )
        semantic_search.return_value = [urbanism]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("عندي مشكل فالكراء")

        self.assertEqual(results[0], rent_result)
        self.assertNotIn("التعمير", results[0].document_title)

    @patch("rag.hybrid_search.search_knowledge_semantic", return_value=[])
    def test_maintenance_query_prefers_family_code_content(self, semantic_search):
        expected = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة الأسرة",
            article_number="المادة 189",
            content="تشمل النفقة الغذاء والكسوة والعلاج وما يعتبر من الضروريات.",
        )

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("شنو هي النفقة؟")

        self.assertEqual(results[0], expected)
        self.assertIn("النفقة", results[0].content)

    @patch("rag.hybrid_search.search_knowledge_semantic", return_value=[])
    def test_custody_query_prefers_family_code_content(self, semantic_search):
        expected = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة الأسرة",
            article_number="المادة 163",
            content="الحضانة حفظ الولد مما قد يضره والقيام بتربية المحضون.",
        )

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("شنو هي الحضانة؟")

        self.assertEqual(results[0], expected)
        self.assertIn("الحضانة", results[0].content)

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_defective_product_query_prefers_consumer_law(self, semantic_search):
        wrong = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة الأسرة",
            article_number="المادة 327",
            content="مقتضيات أسرية عامة.",
        )
        expected = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="حماية المستهلك",
            article_number="المادة 5",
            content="يستفيد المستهلك من الضمان عند وجود عيب في المنتوج.",
        )
        semantic_search.return_value = [wrong]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("شريت منتوج فيه عيب شنو ندير؟")

        self.assertEqual(results[0], expected)

    @patch("rag.hybrid_search.search_knowledge_semantic")
    def test_lawyer_query_prefers_legal_profession_document(self, semantic_search):
        wrong = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مدونة التجارة",
            article_number="المادة 1",
            content="مقتضيات تجارية عامة.",
        )
        expected = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="مهنة المحاماة",
            article_number="المادة 1",
            content="يمارس المحامي الاستشارة والنيابة عن الأطراف أمام المحاكم.",
        )
        semantic_search.return_value = [wrong]

        from .hybrid_search import search_knowledge_hybrid

        results = search_knowledge_hybrid("شنو دور المحامي؟")

        self.assertEqual(results[0], expected)


class LlmTests(SimpleTestCase):
    context = "Source 1\nArticle : Article 10.- Charges déductibles"
    fallback_answer = "Réponse structurée sans LLM"

    def test_legal_prompt_requires_plain_text_without_legal_warning(self):
        from .llm import build_legal_prompt

        prompt = build_legal_prompt(
            "Quelles sont les charges déductibles ?",
            self.context,
        )

        self.assertIn("texte brut", prompt)
        self.assertIn("sans syntaxe Markdown", prompt)
        self.assertIn("N’ajoute aucun avertissement juridique", prompt)
        self.assertIn("Selon l’article 10", prompt)

    def test_darija_prompt_requests_latin_character_moroccan_darija(self):
        from .llm import build_legal_prompt

        prompt = build_legal_prompt(
            "chno homa les charges déductibles?", self.context, language="darija"
        )

        self.assertIn("darija marocaine", prompt)
        self.assertIn("caractères latins", prompt)
        self.assertIn("N’utilise pas l’écriture arabe", prompt)
        self.assertIn("7sab Article 10", prompt)

    def test_arabic_prompt_requests_modern_standard_arabic(self):
        from .llm import build_legal_prompt

        prompt = build_legal_prompt(
            "ما هي المصاريف القابلة للخصم؟", self.context, language="ar"
        )

        self.assertIn("لغة عربية فصحى حديثة وواضحة", prompt)
        self.assertIn("حسب المادة Article 10", prompt)

    @patch.dict(os.environ, {"LEXIA_USE_LLM": "false"}, clear=True)
    @patch("rag.llm.OpenAI")
    def test_disabled_llm_uses_structured_answer(self, openai_client):
        from .llm import generate_answer_or_fallback

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, self.fallback_answer)
        openai_client.assert_not_called()

    @patch.dict(
        os.environ,
        {"LEXIA_USE_LLM": "true", "LEXIA_LLM_PROVIDER": "gemini"},
        clear=True,
    )
    @patch("rag.llm.genai.Client")
    def test_missing_gemini_api_key_uses_structured_answer(self, gemini_client):
        from .llm import generate_answer_or_fallback

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, self.fallback_answer)
        gemini_client.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "LEXIA_USE_LLM": "true",
            "LEXIA_LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-4.1-mini",
        },
        clear=True,
    )
    @patch("rag.llm.OpenAI")
    def test_successful_openai_answer_is_used(self, openai_client):
        from .llm import generate_answer_or_fallback

        response = MagicMock()
        response.output_text = "Réponse générée à partir des sources LexIA."
        openai_client.return_value.responses.create.return_value = response

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, "Réponse générée à partir des sources LexIA.")
        openai_client.assert_called_once_with(api_key="test-key")
        call = openai_client.return_value.responses.create.call_args
        self.assertEqual(call.kwargs["model"], "gpt-4.1-mini")
        self.assertIn("Article 10.- Charges déductibles", call.kwargs["input"])

    @patch.dict(
        os.environ,
        {
            "LEXIA_USE_LLM": "true",
            "LEXIA_LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
        },
        clear=True,
    )
    @patch("rag.llm.OpenAI")
    def test_openai_error_uses_structured_answer(self, openai_client):
        from .llm import generate_answer_or_fallback

        openai_client.return_value.responses.create.side_effect = RuntimeError(
            "API unavailable"
        )

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, self.fallback_answer)

    @patch.dict(
        os.environ,
        {
            "LEXIA_USE_LLM": "true",
            "LEXIA_LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-gemini-key",
            "GEMINI_MODEL": "gemini-2.5-flash",
        },
        clear=True,
    )
    @patch("rag.llm.genai.Client")
    def test_successful_gemini_answer_is_used(self, gemini_client):
        from .llm import generate_answer_or_fallback

        response = MagicMock()
        response.text = "Réponse Gemini fondée sur les sources LexIA."
        gemini_client.return_value.models.generate_content.return_value = response

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, "Réponse Gemini fondée sur les sources LexIA.")
        gemini_client.assert_called_once_with(api_key="test-gemini-key")
        call = gemini_client.return_value.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-2.5-flash")
        self.assertIn("Article 10.- Charges déductibles", call.kwargs["contents"])

    @patch.dict(
        os.environ,
        {
            "LEXIA_USE_LLM": "true",
            "LEXIA_LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-gemini-key",
        },
        clear=True,
    )
    @patch("rag.llm.genai.Client")
    def test_gemini_error_uses_structured_answer(self, gemini_client):
        from .llm import generate_answer_or_fallback

        gemini_client.return_value.models.generate_content.side_effect = RuntimeError(
            "Gemini unavailable"
        )

        answer = generate_answer_or_fallback(
            "Quelles sont les charges déductibles ?",
            self.context,
            self.fallback_answer,
        )

        self.assertEqual(answer, self.fallback_answer)


class ApiSanityTests(APITestCase):
    def test_root_returns_clean_json(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "LexIA API")
        self.assertEqual(response.json()["status"], "ok")

    def test_public_read_endpoints_return_success(self):
        for endpoint in (
            "/api/health/",
            "/api/conversations/",
            "/api/feedback/",
            "/api/stats/",
        ):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_chat_invalid_json_fields_return_clean_validation_errors(self):
        for payload, expected_field in (
            ({}, "question"),
            ({"question": ""}, "question"),
            ({"question": "Question", "language": "xx"}, "language"),
            ({"question": "Question", "conversation_id": "abc"}, "conversation_id"),
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/chat/", payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(expected_field, response.json())


class RagPipelineTests(TestCase):
    def setUp(self):
        self.category = LegalCategory.objects.create(
            name="Fiscalité pipeline",
            slug="fiscalite-pipeline",
        )
        self.entry = KnowledgeEntry.objects.create(
            category=self.category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10.- Charges déductibles",
            title="Charges déductibles",
            content="Les charges déductibles réduisent le résultat fiscal.",
            page_start=31,
        )

    @patch("rag.pipeline.search_knowledge_hybrid")
    @patch("rag.pipeline.is_llm_enabled", return_value=False)
    def test_legal_sources_use_structured_mode(self, llm_enabled, search):
        from .pipeline import run_rag_pipeline

        search.return_value = [self.entry]
        result = run_rag_pipeline("Quelles sont les charges déductibles ?")

        self.assertEqual(result["answer_mode"], "structured")
        self.assertTrue(result["sources"])

    def test_sanctions_article_does_not_use_deductible_expenses_template(self):
        from .pipeline import build_structured_answer

        source = {
            "document_title": "Code Général des Impôts 2024",
            "article_number": "Article 193.- Sanctions et infractions",
            "title": "Sanctions et infractions",
            "category": "Fiscalité",
            "content": (
                "Les infractions aux obligations fiscales donnent lieu aux "
                "sanctions prévues par le présent article."
            ),
            "excerpt": "Les infractions fiscales donnent lieu à des sanctions.",
        }

        answer = build_structured_answer(
            "ما هي الضريبة على الشركات؟", [source], language="ar"
        )

        self.assertNotIn("charges déductibles", answer.casefold())
        self.assertNotIn("المصاريف القابلة للخصم", answer)
        self.assertIn("مقتضيات ضريبية", answer)
        self.assertIn("Article 193", answer)

    @patch("rag.pipeline.search_knowledge_hybrid", return_value=[])
    def test_no_sources_use_fallback_mode(self, search):
        from .pipeline import run_rag_pipeline

        result = run_rag_pipeline("Question fiscale sans résultat")

        self.assertEqual(result["answer_mode"], "fallback")
        self.assertEqual(result["sources"], [])

    @patch("rag.pipeline.generate_answer_or_fallback", return_value="Réponse LLM")
    @patch("rag.pipeline.is_llm_enabled", return_value=True)
    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_openai_success_uses_llm_mode(self, search, llm_enabled, generate):
        from .pipeline import run_rag_pipeline

        search.return_value = [self.entry]
        result = run_rag_pipeline("Quelles sont les charges déductibles ?")

        self.assertEqual(result["answer"], "Réponse LLM")
        self.assertEqual(result["answer_mode"], "llm")
        self.assertIn("Article 10", generate.call_args.args[1])

    @patch("rag.pipeline.generate_answer_or_fallback")
    @patch("rag.pipeline.is_llm_enabled", return_value=True)
    @patch("rag.pipeline.search_knowledge_hybrid")
    def test_openai_failure_uses_structured_mode(
        self, search, llm_enabled, generate
    ):
        from .pipeline import run_rag_pipeline

        search.return_value = [self.entry]
        generate.side_effect = lambda question, context, fallback, language: fallback
        result = run_rag_pipeline("Quelles sont les charges déductibles ?")

        self.assertEqual(result["answer_mode"], "structured")
        self.assertIn("Article 10", result["answer"])

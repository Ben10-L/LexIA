import os
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from knowledge.models import KnowledgeEntry, LegalCategory


class HealthApiTests(APITestCase):
    def setUp(self):
        category = LegalCategory.objects.create(
            name="Fiscalité santé",
            slug="fiscalite-sante",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10",
            content="Charges déductibles.",
            embedding_id="knowledge-entry-1",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 11",
            content="Charges non déductibles.",
        )

    @patch.dict(
        os.environ,
        {
            "LEXIA_USE_LLM": "true",
            "LEXIA_LLM_PROVIDER": "gemini",
            "GEMINI_MODEL": "gemini-3.6-flash",
            "GEMINI_API_KEY": "secret-test-key",
        },
    )
    def test_health_endpoint_returns_200_with_expected_fields(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "database": "ok",
                "knowledge_entries_count": 2,
                "categories_count": 1,
                "chroma_indexed_entries_count": 1,
                "llm_enabled": True,
                "llm_provider": "gemini",
                "llm_model": "gemini-3.6-flash",
            },
        )

    @patch.dict(
        os.environ,
        {
            "LEXIA_LLM_PROVIDER": "openai",
            "OPENAI_MODEL": "gpt-4.1-mini",
        },
    )
    def test_health_uses_the_selected_provider_model(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.json()["llm_provider"], "openai")
        self.assertEqual(response.json()["llm_model"], "gpt-4.1-mini")

    @patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "gemini-secret-value",
            "OPENAI_API_KEY": "openai-secret-value",
        },
    )
    def test_health_response_does_not_expose_api_keys(self):
        response = self.client.get("/api/health/")
        response_text = response.content.decode()

        self.assertNotIn("gemini-secret-value", response_text)
        self.assertNotIn("openai-secret-value", response_text)
        self.assertNotIn("API_KEY", response_text)

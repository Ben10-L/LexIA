from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Conversation, Message


class ConversationHistoryTests(APITestCase):
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

    def test_chat_creates_a_conversation(self):
        response = self.client.post(
            "/api/chat/",
            {"question": "Question sans résultat", "language": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Conversation.objects.count(), 1)
        conversation = Conversation.objects.get()
        self.assertEqual(response.json()["conversation_id"], conversation.id)
        self.assertTrue(conversation.session_id)

    def test_chat_creates_user_and_assistant_messages(self):
        self.client.post(
            "/api/chat/",
            {"question": "Question sans résultat", "language": "fr"},
            format="json",
        )

        messages = list(Message.objects.order_by("created_at", "id"))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, Message.Role.USER)
        self.assertEqual(messages[0].content, "Question sans résultat")
        self.assertEqual(messages[0].sources, [])
        self.assertEqual(messages[1].role, Message.Role.ASSISTANT)
        self.assertEqual(messages[1].sources, [])

    def test_chat_appends_messages_to_an_existing_conversation(self):
        conversation = Conversation.objects.create(
            session_id="existing-session",
            language="fr",
        )

        response = self.client.post(
            "/api/chat/",
            {
                "question": "Autre question sans résultat",
                "language": "fr",
                "conversation_id": conversation.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["conversation_id"], conversation.id)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(conversation.messages.count(), 2)

    def test_conversation_list_returns_latest_first(self):
        older = Conversation.objects.create(session_id="older", language="fr")
        newer = Conversation.objects.create(session_id="newer", language="fr")
        Conversation.objects.filter(pk=older.pk).update(
            updated_at=timezone.now() - timedelta(days=1)
        )

        response = self.client.get("/api/conversations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["id"], newer.id)
        self.assertEqual(response.json()[1]["id"], older.id)

    def test_conversation_detail_returns_messages(self):
        conversation = Conversation.objects.create(
            session_id="detail-session",
            language="fr",
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content="Ma question",
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content="La réponse",
            sources=[{"document_title": "Document juridique"}],
        )

        response = self.client.get(f"/api/conversations/{conversation.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], conversation.id)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["role"], Message.Role.USER)
        self.assertEqual(data["messages"][1]["role"], Message.Role.ASSISTANT)
        self.assertEqual(
            data["messages"][1]["sources"],
            [{"document_title": "Document juridique"}],
        )

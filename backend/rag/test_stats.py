from rest_framework import status
from rest_framework.test import APITestCase

from conversations.models import Conversation, Message
from feedback.models import Feedback
from knowledge.models import KnowledgeEntry, LegalCategory


class StatsApiTests(APITestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(
            session_id="stats-session",
            language="fr",
        )
        self.user_messages = [
            Message.objects.create(
                conversation=self.conversation,
                role=Message.Role.USER,
                content=f"Question {index}",
            )
            for index in range(1, 7)
        ]
        self.assistant_message = Message.objects.create(
            conversation=self.conversation,
            role=Message.Role.ASSISTANT,
            content="Réponse LexIA",
        )
        Feedback.objects.create(
            message=self.assistant_message,
            rating=Feedback.Rating.POSITIVE,
        )
        Feedback.objects.create(
            message=self.assistant_message,
            rating=Feedback.Rating.NEGATIVE,
        )
        category = LegalCategory.objects.create(
            name="Fiscalité statistiques",
            slug="fiscalite-statistiques",
        )
        KnowledgeEntry.objects.create(
            category=category,
            document_title="Code Général des Impôts 2024",
            article_number="Article 10",
            content="Charges déductibles.",
        )

    def test_stats_endpoint_returns_200(self):
        response = self.client.get("/api/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stats_counts_are_correct(self):
        response = self.client.get("/api/stats/")

        self.assertEqual(
            {
                key: response.json()[key]
                for key in (
                    "conversations_count",
                    "messages_count",
                    "assistant_messages_count",
                    "user_messages_count",
                    "feedback_count",
                    "positive_feedback_count",
                    "negative_feedback_count",
                    "knowledge_entries_count",
                    "categories_count",
                )
            },
            {
                "conversations_count": 1,
                "messages_count": 7,
                "assistant_messages_count": 1,
                "user_messages_count": 6,
                "feedback_count": 2,
                "positive_feedback_count": 1,
                "negative_feedback_count": 1,
                "knowledge_entries_count": 1,
                "categories_count": 1,
            },
        )

    def test_recent_questions_returns_latest_five_user_messages_only(self):
        response = self.client.get("/api/stats/")
        recent_questions = response.json()["recent_questions"]

        self.assertEqual(len(recent_questions), 5)
        self.assertEqual(
            [question["content"] for question in recent_questions],
            ["Question 6", "Question 5", "Question 4", "Question 3", "Question 2"],
        )
        self.assertNotIn(
            self.assistant_message.id,
            [question["id"] for question in recent_questions],
        )
        self.assertTrue(all(question["created_at"] for question in recent_questions))

from rest_framework import status
from rest_framework.test import APITestCase

from conversations.models import Conversation, Message

from .models import Feedback


class FeedbackApiTests(APITestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(
            session_id="feedback-test-session",
            language="fr",
        )
        self.user_message = Message.objects.create(
            conversation=self.conversation,
            role=Message.Role.USER,
            content="Question juridique",
        )
        self.assistant_message = Message.objects.create(
            conversation=self.conversation,
            role=Message.Role.ASSISTANT,
            content="Réponse juridique",
        )

    def test_creates_feedback_for_assistant_message(self):
        response = self.client.post(
            "/api/feedback/",
            {
                "message": self.assistant_message.id,
                "rating": "positive",
                "comment": "Réponse utile",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Feedback.objects.count(), 1)
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.message, self.assistant_message)
        self.assertEqual(feedback.rating, Feedback.Rating.POSITIVE)
        self.assertEqual(feedback.comment, "Réponse utile")
        self.assertEqual(response.json()["id"], feedback.id)
        self.assertIn("created_at", response.json())

    def test_rejects_feedback_for_user_message(self):
        response = self.client.post(
            "/api/feedback/",
            {
                "message": self.user_message.id,
                "rating": "negative",
                "comment": "Commentaire",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertFalse(Feedback.objects.exists())

    def test_rejects_invalid_rating(self):
        response = self.client.post(
            "/api/feedback/",
            {
                "message": self.assistant_message.id,
                "rating": "neutral",
                "comment": "Commentaire",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rating", response.json())
        self.assertFalse(Feedback.objects.exists())

    def test_lists_feedback_latest_first(self):
        first = Feedback.objects.create(
            message=self.assistant_message,
            rating=Feedback.Rating.POSITIVE,
            comment="Premier",
        )
        second = Feedback.objects.create(
            message=self.assistant_message,
            rating=Feedback.Rating.NEGATIVE,
            comment="Deuxième",
        )

        response = self.client.get("/api/feedback/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["id"], second.id)
        self.assertEqual(response.json()[1]["id"], first.id)

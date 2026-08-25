from rest_framework import serializers

from conversations.models import Message

from .models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ("id", "message", "rating", "comment", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_message(self, message):
        if message.role != Message.Role.ASSISTANT:
            raise serializers.ValidationError(
                "Le feedback est autorisé uniquement pour les messages de l’assistant."
            )
        return message

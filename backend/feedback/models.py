from django.db import models


class Feedback(models.Model):
    class Rating(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEGATIVE = "negative", "Negative"

    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    rating = models.CharField(max_length=10, choices=Rating.choices)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_rating_display()} feedback for message {self.message_id}"

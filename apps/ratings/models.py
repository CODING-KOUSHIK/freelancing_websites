"""Ratings app — Post-session ratings, feedback, abuse reports"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from apps.core.models import TimestampedModel


class Rating(TimestampedModel):
    """Rating submitted after a recording session ends."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "recordings.RecordingSession",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_given",
    )
    ratee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_received",
    )
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 (Poor) to 5 (Excellent)",
    )
    feedback = models.TextField(max_length=1000, blank=True)

    # ─── Abuse reporting ──────────────────────────────────────
    is_abuse_report = models.BooleanField(default=False)
    abuse_reason = models.CharField(max_length=200, blank=True)
    abuse_reviewed = models.BooleanField(default=False)
    abuse_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_abuse_reports",
    )

    class Meta:
        verbose_name = "Rating"
        verbose_name_plural = "Ratings"
        unique_together = ("session", "rater")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ratee", "-created_at"]),
            models.Index(fields=["is_abuse_report", "abuse_reviewed"]),
        ]

    def __str__(self):
        return f"Rating {self.score}★ by {self.rater.email} → {self.ratee.email}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_reputation()

    def _update_reputation(self):
        """Recalculate ratee's reputation score."""
        from django.db.models import Avg
        avg = Rating.objects.filter(
            ratee=self.ratee,
            is_abuse_report=False,
        ).aggregate(avg=Avg("score"))["avg"] or 0
        self.ratee.reputation_score = round(avg, 2)
        self.ratee.save(update_fields=["reputation_score"])

"""Notifications app — In-app notification center"""
import uuid
from django.db import models
from django.conf import settings
from apps.core.models import TimestampedModel


class Notification(TimestampedModel):
    """In-app notification pushed to a user."""
    TYPE_CHOICES = [
        ("recording_request", "Recording Request"),
        ("recording_accepted", "Recording Accepted"),
        ("recording_rejected", "Recording Rejected"),
        ("recording_completed", "Recording Completed"),
        ("earnings_credited", "Earnings Credited"),
        ("withdrawal_approved", "Withdrawal Approved"),
        ("withdrawal_rejected", "Withdrawal Rejected"),
        ("withdrawal_paid", "Withdrawal Paid"),
        ("ticket_reply", "Ticket Reply"),
        ("ticket_resolved", "Ticket Resolved"),
        ("achievement_earned", "Achievement Earned"),
        ("rating_received", "Rating Received"),
        ("system", "System Notification"),
        ("warning", "Warning"),
        ("referral_bonus", "Referral Bonus"),
        ("daily_reward", "Daily Reward"),
        ("challenge_completed", "Challenge Completed"),
        ("kyc_approved", "KYC Approved"),
        ("kyc_rejected", "KYC Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    title = models.CharField(max_length=300)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    action_url = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
        ]

    def __str__(self):
        status = "📬" if not self.is_read else "📭"
        return f"{status} [{self.notification_type}] → {self.user.email}"

    @classmethod
    def send(cls, user, notification_type, title, message, payload=None, action_url=""):
        """Create notification and push via WebSocket."""
        notif = cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            payload=payload or {},
            action_url=action_url,
        )
        # Async push via Channels
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        try:
            async_to_sync(channel_layer.group_send)(
                f"notifications_{user.pk}",
                {
                    "type": "notification_push",
                    "id": str(notif.id),
                    "notification_type": notification_type,
                    "title": title,
                    "message": message,
                    "payload": payload or {},
                    "action_url": action_url,
                    "created_at": notif.created_at.isoformat(),
                },
            )
        except Exception:
            pass  # Don't fail if channel layer unavailable
        return notif

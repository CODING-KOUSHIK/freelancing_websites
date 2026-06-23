"""Presence app — Real-time online/offline tracking"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class UserPresence(models.Model):
    """One-to-one real-time presence record per user."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence",
        primary_key=True,
    )
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now)
    channel_name = models.CharField(max_length=255, blank=True)  # Channels channel name
    session_key = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "User Presence"
        verbose_name_plural = "User Presences"
        indexes = [
            models.Index(fields=["is_online", "-last_seen"]),
        ]

    def __str__(self):
        status = "🟢 Online" if self.is_online else f"⚫ Last seen {self.last_seen:%Y-%m-%d %H:%M}"
        return f"{self.user.full_name} — {status}"

    def mark_online(self, channel_name=""):
        self.is_online = True
        self.channel_name = channel_name
        self.last_seen = timezone.now()
        self.save(update_fields=["is_online", "channel_name", "last_seen"])

    def mark_offline(self):
        self.is_online = False
        self.last_seen = timezone.now()
        self.channel_name = ""
        self.save(update_fields=["is_online", "last_seen", "channel_name"])

    @property
    def last_seen_display(self):
        """Human-readable last seen string."""
        if self.is_online:
            return "Online now"
        delta = timezone.now() - self.last_seen
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"

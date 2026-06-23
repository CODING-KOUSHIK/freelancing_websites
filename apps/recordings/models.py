"""Recordings app — Session management, WebRTC signaling, metadata"""
import uuid
from django.db import models
from django.conf import settings
from apps.core.models import TimestampedModel


def recording_file_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"recordings/{instance.session_id}/{uuid.uuid4()}.{ext}"


class RecordingSession(TimestampedModel):
    """Core recording session between two users."""
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("in_progress", "In Progress"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    UPLOAD_STATUS_CHOICES = [
        ("pending", "Pending Upload"),
        ("uploading", "Uploading"),
        ("uploaded", "Uploaded"),
        ("failed", "Upload Failed"),
        ("retrying", "Retrying"),
    ]

    QUALITY_CHOICES = [
        ("16kHz", "16kHz / 16-bit"),
        ("48kHz", "48kHz / 16-bit"),
    ]

    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="sessions_as_a",
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name="sessions_as_b",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested", db_index=True)
    sample_rate = models.CharField(max_length=10, choices=QUALITY_CHOICES, default="48kHz")

    # ─── Timing ───────────────────────────────────────────────
    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    # ─── Files ────────────────────────────────────────────────
    channel_a_file = models.FileField(upload_to=recording_file_path, null=True, blank=True)
    channel_b_file = models.FileField(upload_to=recording_file_path, null=True, blank=True)
    mixed_file = models.FileField(upload_to=recording_file_path, null=True, blank=True)
    file_format = models.CharField(max_length=10, default="wav")
    file_size_bytes = models.BigIntegerField(default=0)

    # ─── Quality & Scoring ────────────────────────────────────
    quality_score = models.FloatField(null=True, blank=True)
    signal_to_noise = models.FloatField(null=True, blank=True)
    quality_flags = models.JSONField(default=list, blank=True)

    # ─── Google Drive ─────────────────────────────────────────
    drive_file_id = models.CharField(max_length=255, blank=True)
    drive_link = models.URLField(blank=True)
    drive_folder_id = models.CharField(max_length=255, blank=True)
    upload_status = models.CharField(max_length=20, choices=UPLOAD_STATUS_CHOICES, default="pending")
    upload_attempts = models.IntegerField(default=0)
    last_upload_attempt = models.DateTimeField(null=True, blank=True)

    # ─── Earnings ─────────────────────────────────────────────
    earnings_calculated = models.BooleanField(default=False)
    earnings_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_minute_rate_used = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # ─── Metadata ─────────────────────────────────────────────
    metadata = models.JSONField(default=dict, blank=True)
    room_name = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Recording Session"
        verbose_name_plural = "Recording Sessions"
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["user_a", "-requested_at"]),
            models.Index(fields=["user_b", "-requested_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["upload_status"]),
        ]

    def __str__(self):
        return f"Session {str(self.session_id)[:8]} | {self.user_a} ↔ {self.user_b} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.room_name:
            self.room_name = f"room_{str(self.session_id)[:12]}"
        super().save(*args, **kwargs)

    @property
    def duration_display(self):
        minutes, seconds = divmod(self.duration_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"


class WebRTCSignal(models.Model):
    """WebRTC signaling messages stored for session establishment."""
    SIGNAL_TYPES = [
        ("offer", "SDP Offer"),
        ("answer", "SDP Answer"),
        ("ice_candidate", "ICE Candidate"),
        ("hang_up", "Hang Up"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(RecordingSession, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=20, choices=SIGNAL_TYPES)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "WebRTC Signal"
        indexes = [models.Index(fields=["session", "signal_type"])]

    def __str__(self):
        return f"{self.signal_type} from {self.sender} in {self.session.session_id}"


class RecordingChunk(TimestampedModel):
    """Auto-saved recording chunks for network recovery."""
    session = models.ForeignKey(RecordingSession, on_delete=models.CASCADE, related_name="chunks")
    channel = models.CharField(max_length=1, choices=[("a", "Channel A"), ("b", "Channel B")])
    chunk_index = models.IntegerField()
    file = models.FileField(upload_to="chunks/")
    duration_seconds = models.FloatField(default=0)
    is_uploaded = models.BooleanField(default=False)

    class Meta:
        unique_together = ("session", "channel", "chunk_index")
        ordering = ["chunk_index"]

    def __str__(self):
        return f"Chunk {self.chunk_index} Ch{self.channel} — {self.session.session_id}"

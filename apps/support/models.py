"""Support app — Tickets, replies, internal notes"""
import uuid
from django.db import models
from django.conf import settings
from apps.core.models import TimestampedModel


def ticket_attachment_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"support/tickets/{instance.ticket.pk}/{uuid.uuid4()}.{ext}"


def reply_attachment_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"support/replies/{instance.ticket.pk}/{uuid.uuid4()}.{ext}"


class SupportTicket(TimestampedModel):
    """User support ticket with full lifecycle management."""
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting_user", "Waiting for User"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    CATEGORY_CHOICES = [
        ("account", "Account Issues"),
        ("payment", "Payment / Withdrawal"),
        ("recording", "Recording Problems"),
        ("technical", "Technical Issues"),
        ("abuse", "Abuse Report"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    title = models.CharField(max_length=300)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium", db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_tickets",
        limit_choices_to={"is_staff": True},
    )
    first_response_at = models.DateTimeField(null=True, blank=True)
    last_response_at = models.DateTimeField(null=True, blank=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    escalation_level = models.PositiveIntegerField(default=0)
    escalated_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        return f"[{self.ticket_number}] {self.title} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import random
            self.ticket_number = f"TKT-{random.randint(100000, 999999)}"
        if not self.sla_due_at:
            from django.utils import timezone
            sla_hours = {
                "low": 72,
                "medium": 24,
                "high": 8,
                "urgent": 2,
            }.get(self.priority, 24)
            self.sla_due_at = timezone.now() + timezone.timedelta(hours=sla_hours)
        super().save(*args, **kwargs)


class TicketReply(TimestampedModel):
    """Thread reply to a support ticket."""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to=reply_attachment_path, null=True, blank=True)
    is_internal_note = models.BooleanField(default=False, help_text="Visible to staff only")

    class Meta:
        verbose_name = "Ticket Reply"
        verbose_name_plural = "Ticket Replies"
        ordering = ["created_at"]

    def __str__(self):
        kind = "🔒 Note" if self.is_internal_note else "💬 Reply"
        return f"{kind} by {self.author.email} on #{self.ticket.ticket_number}"

"""Core app — Shared models: AuditLog, SiteSettings, Achievements, Referrals"""
import uuid
from django.db import models
from django.conf import settings


class TimestampedModel(models.Model):
    """Abstract base with created_at / updated_at timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(models.Model):
    """Admin-configurable key-value settings store."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default


class AuditLog(models.Model):
    """Immutable audit trail of user/admin actions."""
    ACTION_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("register", "Register"),
        ("profile_update", "Profile Update"),
        ("kyc_submit", "KYC Submitted"),
        ("recording_start", "Recording Start"),
        ("recording_end", "Recording End"),
        ("withdrawal_request", "Withdrawal Request"),
        ("admin_action", "Admin Action"),
        ("api_access", "API Access"),
        ("failed_login", "Failed Login"),
        ("password_reset", "Password Reset"),
        ("otp_sent", "OTP Sent"),
        ("otp_verified", "OTP Verified"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
            models.Index(fields=["ip_address"]),
        ]

    def __str__(self):
        return f"[{self.action}] {self.user} @ {self.created_at:%Y-%m-%d %H:%M}"


class Achievement(TimestampedModel):
    """Gamification achievement definitions."""
    CONDITION_TYPES = [
        ("recordings_count", "Recordings Count"),
        ("hours_recorded", "Hours Recorded"),
        ("rating_avg", "Average Rating"),
        ("referrals_count", "Referrals Count"),
        ("earnings_total", "Total Earnings"),
        ("streak_days", "Login Streak Days"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, default="🏆")
    badge_color = models.CharField(max_length=20, default="#FFD700")
    condition_type = models.CharField(max_length=50, choices=CONDITION_TYPES)
    condition_value = models.FloatField(help_text="Threshold to unlock this achievement")
    points = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Achievement"
        verbose_name_plural = "Achievements"
        ordering = ["condition_value"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserAchievement(TimestampedModel):
    """Many-to-many relationship: which users earned which achievements."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="user_achievements",
    )
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "achievement")
        verbose_name = "User Achievement"

    def __str__(self):
        return f"{self.user} — {self.achievement}"


class Referral(TimestampedModel):
    """Tracks referral relationships and bonus status."""
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_source",
    )
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_paid = models.BooleanField(default=False)
    bonus_paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Referral"
        verbose_name_plural = "Referrals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} → {self.referred_user}"


class WeeklyChallenge(TimestampedModel):
    """Admin-created weekly challenges with reward conditions."""
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    goal_type = models.CharField(max_length=50)
    goal_value = models.FloatField()
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Weekly Challenge"
        verbose_name_plural = "Weekly Challenges"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} ({self.start_date} - {self.end_date})"


class UserChallengeProgress(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    challenge = models.ForeignKey(WeeklyChallenge, on_delete=models.CASCADE)
    current_value = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    reward_credited = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "challenge")

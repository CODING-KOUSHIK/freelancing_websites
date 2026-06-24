"""Accounts app — CustomUser, EmailOTP, Login History, KYC"""
import uuid
import random
import string
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimestampedModel


def generate_referral_code():
    """Generate unique 8-char alphanumeric referral code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def user_photo_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"profiles/{instance.pk}/{uuid.uuid4()}.{ext}"


def kyc_document_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"kyc/{instance.user.pk}/{uuid.uuid4()}.{ext}"


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Primary user model for the AI Voice Data Marketplace."""

    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer not to say"),
    ]

    LEVEL_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("expert", "Expert"),
        ("verified_expert", "Verified Expert"),
    ]

    KYC_STATUS_CHOICES = [
        ("not_submitted", "Not Submitted"),
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    # ─── Core fields ─────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(_("full name"), max_length=200)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to=user_photo_path, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    language = models.CharField(max_length=10, default="en")

    # ─── Status & Verification ────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # email verified
    is_profile_verified = models.BooleanField(default=False)  # admin verified
    is_suspended = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default="not_submitted")

    # ─── Gamification ─────────────────────────────────────────
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="beginner")
    reputation_score = models.FloatField(default=0.0)
    login_streak = models.IntegerField(default=0)
    last_login_date = models.DateField(null=True, blank=True)

    # ─── Referral ─────────────────────────────────────────────
    referral_code = models.CharField(max_length=20, unique=True, default=generate_referral_code)
    referred_by = models.ForeignKey(
        "self",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )

    # ─── Settings ─────────────────────────────────────────────
    dark_mode = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    whatsapp_notifications = models.BooleanField(default=False)
    auto_accept_requests = models.BooleanField(default=False)
    preferred_language = models.CharField(max_length=10, default="en")

    # ─── Timestamps ───────────────────────────────────────────
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["referral_code"]),
            models.Index(fields=["level"]),
            models.Index(fields=["-reputation_score"]),
        ]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def profile_completion(self):
        """Calculate % of profile fields filled in."""
        fields = [
            self.full_name, self.gender, self.whatsapp_number,
            self.date_of_birth, self.country, self.profile_photo,
            self.bio,
        ]
        filled = sum(1 for f in fields if f)
        return int((filled / len(fields)) * 100)

    @property
    def short_name(self):
        parts = self.full_name.split()
        return parts[0] if parts else self.email.split("@")[0]

    def get_full_name(self):
        return self.full_name

    def update_login_streak(self):
        from datetime import date
        today = date.today()
        if self.last_login_date:
            delta = (today - self.last_login_date).days
            if delta == 1:
                self.login_streak += 1
            elif delta > 1:
                self.login_streak = 1
        else:
            self.login_streak = 1
        self.last_login_date = today
        self.save(update_fields=["login_streak", "last_login_date"])


class EmailOTP(TimestampedModel):
    """Email-based OTP for verification and password reset."""
    PURPOSE_CHOICES = [
        ("email_verify", "Email Verification"),
        ("password_reset", "Password Reset"),
        ("login", "Login OTP"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="otps")
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="email_verify")
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Email OTP"
        verbose_name_plural = "Email OTPs"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "is_used"])]

    def __str__(self):
        return f"OTP:{self.otp_code} for {self.user.email} [{self.purpose}]"

    @property
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    def generate(cls, user, purpose="email_verify", expiry_minutes=10):
        from django.conf import settings
        import os
        # BYPASS_OTP=True → use fixed "000000" (for testing when no email service)
        # Set BYPASS_OTP=False in Railway when real email is ready
        if os.environ.get("BYPASS_OTP", "True").lower() in ("true", "1", "yes"):
            code = "000000"
        else:
            code = "".join(random.choices(string.digits, k=6))
        exp = timezone.now() + timezone.timedelta(
            minutes=getattr(settings, "OTP_EXPIRY_MINUTES", expiry_minutes)
        )
        # Invalidate previous unused OTPs for same purpose
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        return cls.objects.create(user=user, otp_code=code, purpose=purpose, expires_at=exp)


class LoginHistory(TimestampedModel):
    """Track all login attempts per user."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="login_history")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=200, blank=True)
    success = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Login History"
        verbose_name_plural = "Login History"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.user.email} from {self.ip_address}"


class DeviceTracking(TimestampedModel):
    """Track known devices per user for security alerts."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="devices")
    device_fingerprint = models.CharField(max_length=255)
    device_name = models.CharField(max_length=200, blank=True)
    is_trusted = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "device_fingerprint")
        verbose_name = "Device"
        verbose_name_plural = "Devices"


class KYCDocument(TimestampedModel):
    """KYC verification documents uploaded by user."""
    DOC_TYPE_CHOICES = [
        ("aadhaar", "Aadhaar Card"),
        ("pan", "PAN Card"),
        ("passport", "Passport"),
        ("driving_license", "Driving License"),
        ("voter_id", "Voter ID"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="kyc_documents")
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    document_front = models.ImageField(upload_to=kyc_document_path)
    document_back = models.ImageField(upload_to=kyc_document_path, blank=True, null=True)
    doc_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="kyc_reviews",
    )

    class Meta:
        verbose_name = "KYC Document"
        verbose_name_plural = "KYC Documents"
        ordering = ["-created_at"]

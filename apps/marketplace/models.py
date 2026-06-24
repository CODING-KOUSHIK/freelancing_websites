"""Enterprise marketplace models."""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimestampedModel


def marketplace_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"marketplace/{instance._meta.model_name}/{instance.pk or 'draft'}/{uuid.uuid4()}.{ext}"


def job_media_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"marketplace/jobs/{instance.job.job_id}/{uuid.uuid4()}.{ext}"


def generate_job_id():
    return f"JOB-{uuid.uuid4().hex[:10].upper()}"


TASK_MODE_CHOICES = [
    ("voice_recording", "Voice Recording"),
    ("survey", "Survey"),
    ("data_collection", "Data Collection"),
    ("data_annotation", "Data Annotation"),
    ("image_labeling", "Image Labeling"),
    ("video_recording", "Video Recording"),
    ("audio_validation", "Audio Validation"),
    ("ai_training", "AI Training"),
    ("transcription", "Transcription"),
    ("translation", "Translation"),
    ("content_writing", "Content Writing"),
    ("app_testing", "App Testing"),
    ("website_testing", "Website Testing"),
    ("product_research", "Product Research"),
    ("lead_generation", "Lead Generation"),
    ("web_scraping", "Web Scraping"),
    ("seo_tasks", "SEO Tasks"),
    ("social_media_tasks", "Social Media Tasks"),
    ("mobile_app_tasks", "Mobile App Tasks"),
    ("manual_review_tasks", "Manual Review Tasks"),
]


class MarketplaceProfile(TimestampedModel):
    """Extended professional profile for workers and recruiters."""

    ROLE_CHOICES = [
        ("worker", "Worker"),
        ("recruiter", "Recruiter"),
        ("both", "Both"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="marketplace_profile",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="worker")
    headline = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    website_url = models.URLField(blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    bio = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    portfolio = models.JSONField(default=list, blank=True)
    work_history = models.JSONField(default=list, blank=True)
    resume = models.FileField(upload_to="marketplace/resumes/", null=True, blank=True)
    xp_points = models.PositiveIntegerField(default=0)
    achievement_badges = models.JSONField(default=list, blank=True)
    daily_reward_streak = models.PositiveIntegerField(default=0)
    last_reward_date = models.DateField(null=True, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Marketplace Profile"
        verbose_name_plural = "Marketplace Profiles"

    def __str__(self):
        return f"{self.user.full_name} marketplace profile"

    @property
    def tier_label(self):
        xp = self.xp_points
        if xp >= 1000:
            return "Elite"
        if xp >= 500:
            return "Expert"
        if xp >= 250:
            return "Professional"
        if xp >= 100:
            return "Contributor"
        return "Beginner"

    def add_xp(self, points):
        self.xp_points = max(0, self.xp_points + int(points))
        self.save(update_fields=["xp_points", "updated_at"])


class MarketplaceCategory(TimestampedModel):
    """Unlimited task/job categories."""

    code = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=150, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    task_mode = models.CharField(max_length=40, choices=TASK_MODE_CHOICES, default="voice_recording")
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=80, blank=True)
    banner_image = models.ImageField(upload_to="marketplace/categories/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
            models.Index(fields=["task_mode"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:120]
        super().save(*args, **kwargs)


class JobPosting(TimestampedModel):
    """Flexible marketplace job definition."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("paused", "Paused"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    PAYMENT_MODEL_CHOICES = [
        ("fixed", "Fixed Amount"),
        ("per_minute", "Per Minute"),
        ("per_hour", "Per Hour"),
        ("per_task", "Per Task"),
        ("per_submission", "Per Submission"),
        ("dynamic_formula", "Dynamic Formula"),
    ]

    SUBMISSION_TYPE_CHOICES = [
        ("file_upload", "File Upload"),
        ("text_submission", "Text Submission"),
        ("audio_upload", "Audio Upload"),
        ("video_upload", "Video Upload"),
        ("image_upload", "Image Upload"),
        ("form_submission", "Form Submission"),
        ("google_form", "Google Form Completion"),
        ("external_api", "External API Validation"),
    ]

    GENDER_CHOICES = [
        ("any", "Any"),
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    job_id = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posted_jobs",
    )
    category = models.ForeignKey(
        MarketplaceCategory,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    subcategory = models.CharField(max_length=150, blank=True)
    title = models.CharField(max_length=250)
    subtitle = models.CharField(max_length=250, blank=True)
    featured_job = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False, db_index=True)
    trending_priority = models.PositiveIntegerField(default=0)
    priority_level = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    short_description = models.TextField(blank=True)
    full_description = models.TextField()
    requirements = models.TextField(blank=True)
    eligibility = models.TextField(blank=True)
    skills_required = models.JSONField(default=list, blank=True)
    age_restriction_min = models.PositiveIntegerField(null=True, blank=True)
    age_restriction_max = models.PositiveIntegerField(null=True, blank=True)
    country_restriction = models.JSONField(default=list, blank=True)
    gender_restriction = models.CharField(max_length=20, choices=GENDER_CHOICES, default="any")
    language_restriction = models.JSONField(default=list, blank=True)
    experience_requirement = models.CharField(max_length=255, blank=True)
    device_requirement = models.CharField(max_length=255, blank=True)
    payment_model = models.CharField(max_length=30, choices=PAYMENT_MODEL_CHOICES, default="fixed")
    currency = models.CharField(max_length=5, default="INR")
    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_minute_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_hour_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_task_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_submission_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dynamic_formula = models.CharField(max_length=255, blank=True)
    daily_limit = models.PositiveIntegerField(null=True, blank=True)
    weekly_limit = models.PositiveIntegerField(null=True, blank=True)
    monthly_limit = models.PositiveIntegerField(null=True, blank=True)
    global_limit = models.PositiveIntegerField(null=True, blank=True)
    user_limit = models.PositiveIntegerField(null=True, blank=True)
    submission_type = models.CharField(max_length=30, choices=SUBMISSION_TYPE_CHOICES, default="text_submission")
    tutorial_pdf = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    tutorial_video_url = models.URLField(blank=True)
    youtube_video_url = models.URLField(blank=True)
    loom_video_url = models.URLField(blank=True)
    external_links = models.JSONField(default=list, blank=True)
    google_form_link = models.URLField(blank=True)
    google_sheet_link = models.URLField(blank=True)
    documentation_url = models.URLField(blank=True)
    instruction_file = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    field_schema = models.JSONField(default=list, blank=True)
    payment_settings = models.JSONField(default=dict, blank=True)
    limit_rules = models.JSONField(default=dict, blank=True)
    submission_rules = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    banner_image = models.ImageField(upload_to="marketplace/jobs/banners/", null=True, blank=True)
    thumbnail = models.ImageField(upload_to="marketplace/jobs/thumbnails/", null=True, blank=True)
    application_deadline = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    response_sla_hours = models.PositiveIntegerField(null=True, blank=True)
    is_private = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "featured_job", "-created_at"]),
            models.Index(fields=["recruiter", "-created_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return f"{self.job_id} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.job_id:
            self.job_id = generate_job_id()
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        if self.status != "published" or self.is_archived:
            return False
        if self.application_deadline and self.application_deadline < timezone.now():
            return False
        return True

    def calculate_payout(self, duration_seconds=0, submissions=1):
        duration_minutes = Decimal(duration_seconds or 0) / Decimal(60)
        if self.payment_model == "fixed":
            return Decimal(self.fixed_amount)
        if self.payment_model == "per_minute":
            return Decimal(self.per_minute_rate) * duration_minutes
        if self.payment_model == "per_hour":
            return Decimal(self.per_hour_rate) * (duration_minutes / Decimal(60))
        if self.payment_model == "per_task":
            return Decimal(self.per_task_rate) * Decimal(submissions)
        if self.payment_model == "per_submission":
            return Decimal(self.per_submission_rate) * Decimal(submissions)
        return Decimal(self.payment_settings.get("base_amount", self.fixed_amount))


class JobMedia(TimestampedModel):
    """Media and attachment records for a job."""

    MEDIA_TYPE_CHOICES = [
        ("image", "Image"),
        ("pdf", "PDF"),
        ("zip", "ZIP"),
        ("video", "Video"),
        ("link", "Link"),
        ("instruction", "Instruction"),
    ]

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to=job_media_upload_path, null=True, blank=True)
    external_url = models.URLField(blank=True)
    caption = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.job.job_id} - {self.media_type}"


class JobApplication(TimestampedModel):
    """User application and workflow tracking for a job."""

    STATUS_CHOICES = [
        ("applied", "Applied"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("assigned", "Assigned"),
        ("submitted", "Submitted"),
        ("verification", "Verification"),
        ("payment_approved", "Payment Approved"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="applied", db_index=True)
    cover_letter = models.TextField(blank=True)
    expected_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_job_applications",
    )
    review_note = models.TextField(blank=True)
    submission_note = models.TextField(blank=True)
    verification_note = models.TextField(blank=True)
    workflow_payload = models.JSONField(default=dict, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    creator_payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    payment_approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("job", "applicant")
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["applicant", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.job.job_id} - {self.applicant.email}"

    @property
    def progress_percent(self):
        mapping = {
            "applied": 10,
            "under_review": 25,
            "approved": 40,
            "assigned": 55,
            "submitted": 70,
            "verification": 80,
            "payment_approved": 90,
            "completed": 100,
            "rejected": 0,
            "cancelled": 0,
        }
        return mapping.get(self.status, 0)


class JobSubmission(TimestampedModel):
    """Concrete submission payload for an application."""

    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("needs_revision", "Needs Revision"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="submissions")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_submissions",
    )
    submission_type = models.CharField(max_length=30, choices=JobPosting.SUBMISSION_TYPE_CHOICES)
    text_content = models.TextField(blank=True)
    file_upload = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    audio_upload = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    video_upload = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    image_upload = models.FileField(upload_to=marketplace_upload_path, null=True, blank=True)
    external_url = models.URLField(blank=True)
    form_payload = models.JSONField(default=dict, blank=True)
    verification_status = models.CharField(
        max_length=30,
        choices=VERIFICATION_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_job_submissions",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["application", "-created_at"]),
            models.Index(fields=["verification_status", "payment_status"]),
        ]

    def __str__(self):
        return f"Submission {self.id} for {self.application.job.job_id}"


class SavedJob(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_jobs")
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="saved_by")

    class Meta:
        unique_together = ("user", "job")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} saved {self.job.job_id}"


class JobFollow(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_jobs")
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="followers")

    class Meta:
        unique_together = ("user", "job")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} follows {self.job.job_id}"


class RecruiterFollow(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_recruiters")
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )

    class Meta:
        unique_together = ("user", "recruiter")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} follows recruiter {self.recruiter.email}"


class DynamicSetting(TimestampedModel):
    """Typed, editable settings for the super settings engine."""

    VALUE_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("json", "JSON"),
        ("url", "URL"),
        ("markdown", "Markdown"),
    ]

    group = models.CharField(max_length=100, default="general", db_index=True)
    key = models.SlugField(max_length=120, unique=True)
    label = models.CharField(max_length=200)
    value_type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES, default="text")
    text_value = models.TextField(blank=True)
    number_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    bool_value = models.BooleanField(default=False)
    json_value = models.JSONField(default=dict, blank=True)
    default_text = models.TextField(blank=True)
    default_json = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    is_editable = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["group", "key"]
        indexes = [
            models.Index(fields=["group", "key"]),
            models.Index(fields=["is_public", "is_editable"]),
        ]

    def __str__(self):
        return f"{self.group}:{self.key}"

    @property
    def value(self):
        if self.value_type == "number":
            return self.number_value if self.number_value is not None else self.default_json.get("number")
        if self.value_type == "boolean":
            return self.bool_value
        if self.value_type == "json":
            return self.json_value or self.default_json
        return self.text_value or self.default_text


class NotificationTemplate(TimestampedModel):
    """Templates for email, WhatsApp, and in-app notifications."""

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("notification", "Notification"),
        ("sms", "SMS"),
    ]

    slug = models.SlugField(max_length=120, unique=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    variables = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["channel", "slug"]

    def __str__(self):
        return f"{self.channel}:{self.slug}"


class AnalyticsSnapshot(TimestampedModel):
    """Daily cached analytics for the custom portal."""

    SCOPE_CHOICES = [
        ("portal", "Portal"),
        ("marketplace", "Marketplace"),
        ("wallet", "Wallet"),
        ("recordings", "Recordings"),
    ]

    snapshot_date = models.DateField(unique=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="portal")
    payload = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-snapshot_date"]

    def __str__(self):
        return f"{self.scope} snapshot {self.snapshot_date}"


class FixedTask(TimestampedModel):
    """Internal staff task assignments created and managed by admin."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fixed_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_fixed_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    instructions_file = models.FileField(
        upload_to="marketplace/fixed_tasks/", null=True, blank=True
    )
    submission_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Fixed Task"
        verbose_name_plural = "Fixed Tasks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        assignee = self.assigned_to.full_name if self.assigned_to else "Unassigned"
        return f"{self.title} → {assignee} [{self.status}]"

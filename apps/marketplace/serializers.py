"""Marketplace serializers."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.marketplace.models import (
    AnalyticsSnapshot,
    DynamicSetting,
    JobApplication,
    JobFollow,
    JobMedia,
    JobPosting,
    JobSubmission,
    MarketplaceCategory,
    MarketplaceProfile,
    NotificationTemplate,
    RecruiterFollow,
    SavedJob,
)

User = get_user_model()


class CompactUserSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()
    tier = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "profile_photo",
            "country",
            "reputation_score",
            "level",
            "is_online",
            "tier",
        ]

    def get_is_online(self, obj):
        try:
            return obj.presence.is_online
        except Exception:
            return False

    def get_tier(self, obj):
        try:
            return obj.marketplace_profile.tier_label
        except Exception:
            return "Beginner"


class MarketplaceProfileSerializer(serializers.ModelSerializer):
    user = CompactUserSerializer(read_only=True)
    tier_label = serializers.ReadOnlyField()

    class Meta:
        model = MarketplaceProfile
        fields = [
            "user",
            "role",
            "headline",
            "company_name",
            "website_url",
            "timezone",
            "bio",
            "skills",
            "languages",
            "certifications",
            "education",
            "portfolio",
            "work_history",
            "resume",
            "xp_points",
            "tier_label",
            "achievement_badges",
            "daily_reward_streak",
            "last_reward_date",
            "onboarding_completed",
            "metadata",
        ]
        read_only_fields = ["xp_points", "tier_label"]


class MarketplaceCategorySerializer(serializers.ModelSerializer):
    job_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MarketplaceCategory
        fields = [
            "id",
            "code",
            "name",
            "parent",
            "task_mode",
            "description",
            "icon",
            "banner_image",
            "is_active",
            "sort_order",
            "metadata",
            "job_count",
        ]


class JobMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobMedia
        fields = [
            "id",
            "media_type",
            "title",
            "file",
            "external_url",
            "caption",
            "sort_order",
            "metadata",
        ]


class JobSubmissionSerializer(serializers.ModelSerializer):
    submitted_by = CompactUserSerializer(read_only=True)

    class Meta:
        model = JobSubmission
        fields = [
            "id",
            "submitted_by",
            "submission_type",
            "text_content",
            "file_upload",
            "audio_upload",
            "video_upload",
            "image_upload",
            "external_url",
            "form_payload",
            "verification_status",
            "payment_status",
            "payment_amount",
            "verified_by",
            "verified_at",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "submitted_by",
            "verification_status",
            "payment_status",
            "payment_amount",
            "verified_by",
            "verified_at",
            "created_at",
        ]


class JobApplicationSerializer(serializers.ModelSerializer):
    applicant = CompactUserSerializer(read_only=True)
    job = serializers.SerializerMethodField()
    submissions = JobSubmissionSerializer(many=True, read_only=True)
    progress_percent = serializers.ReadOnlyField()

    def get_job(self, obj):
        """Return compact job info including integer id needed by partner picker."""
        job = obj.job
        if not job:
            return None
        return {
            "id": job.pk,
            "job_id": job.job_id,
            "title": job.title,
            "submission_type": job.submission_type,
            "payment_model": job.payment_model,
            "fixed_amount": str(job.fixed_amount),
            "per_minute_rate": str(job.per_minute_rate),
            "per_hour_rate": str(job.per_hour_rate),
            "per_task_rate": str(job.per_task_rate),
            "per_submission_rate": str(job.per_submission_rate),
            "is_trending": job.is_trending,
            "is_open": job.is_open,
            "category_detail": {
                "name": job.category.name if job.category else "",
                "code": job.category.code if job.category else "",
            },
            "recruiter": {
                "full_name": job.recruiter.full_name if job.recruiter else "",
            },
        }

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "job",
            "applicant",
            "status",
            "cover_letter",
            "expected_rate",
            "assigned_reviewer",
            "review_note",
            "submission_note",
            "verification_note",
            "workflow_payload",
            "gross_amount",
            "platform_fee_amount",
            "creator_payout_amount",
            "applied_at",
            "reviewed_at",
            "assigned_at",
            "submitted_at",
            "verified_at",
            "payment_approved_at",
            "completed_at",
            "progress_percent",
            "submissions",
        ]
        read_only_fields = [
            "applicant",
            "status",
            "review_note",
            "submission_note",
            "verification_note",
            "workflow_payload",
            "gross_amount",
            "platform_fee_amount",
            "creator_payout_amount",
            "applied_at",
            "reviewed_at",
            "assigned_at",
            "submitted_at",
            "verified_at",
            "payment_approved_at",
            "completed_at",
            "progress_percent",
        ]


class JobPostingSerializer(serializers.ModelSerializer):
    recruiter = CompactUserSerializer(read_only=True)
    category_detail = MarketplaceCategorySerializer(source="category", read_only=True)
    media = JobMediaSerializer(many=True, read_only=True)
    applications_count = serializers.SerializerMethodField()
    saved_count = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()

    class Meta:
        model = JobPosting
        fields = [
            "id",
            "job_id",
            "recruiter",
            "category",
            "category_detail",
            "subcategory",
            "title",
            "subtitle",
            "featured_job",
            "priority_level",
            "status",
            "short_description",
            "full_description",
            "requirements",
            "eligibility",
            "skills_required",
            "age_restriction_min",
            "age_restriction_max",
            "country_restriction",
            "gender_restriction",
            "language_restriction",
            "experience_requirement",
            "device_requirement",
            "payment_model",
            "currency",
            "fixed_amount",
            "per_minute_rate",
            "per_hour_rate",
            "per_task_rate",
            "per_submission_rate",
            "dynamic_formula",
            "daily_limit",
            "weekly_limit",
            "monthly_limit",
            "global_limit",
            "user_limit",
            "submission_type",
            "tutorial_pdf",
            "tutorial_video_url",
            "youtube_video_url",
            "loom_video_url",
            "external_links",
            "google_form_link",
            "google_sheet_link",
            "documentation_url",
            "instruction_file",
            "field_schema",
            "payment_settings",
            "limit_rules",
            "submission_rules",
            "metadata",
            "banner_image",
            "thumbnail",
            "application_deadline",
            "starts_at",
            "ends_at",
            "published_at",
            "estimated_duration_minutes",
            "response_sla_hours",
            "is_private",
            "is_archived",
            "media",
            "applications_count",
            "saved_count",
            "follower_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "job_id",
            "recruiter",
            "published_at",
            "created_at",
            "updated_at",
            "applications_count",
            "saved_count",
            "follower_count",
        ]

    def get_applications_count(self, obj):
        return obj.applications.count()

    def get_saved_count(self, obj):
        return obj.saved_by.count()

    def get_follower_count(self, obj):
        return obj.followers.count()


class JobPostingWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosting
        fields = [
            "category",
            "subcategory",
            "title",
            "subtitle",
            "featured_job",
            "priority_level",
            "status",
            "short_description",
            "full_description",
            "requirements",
            "eligibility",
            "skills_required",
            "age_restriction_min",
            "age_restriction_max",
            "country_restriction",
            "gender_restriction",
            "language_restriction",
            "experience_requirement",
            "device_requirement",
            "payment_model",
            "currency",
            "fixed_amount",
            "per_minute_rate",
            "per_hour_rate",
            "per_task_rate",
            "per_submission_rate",
            "dynamic_formula",
            "daily_limit",
            "weekly_limit",
            "monthly_limit",
            "global_limit",
            "user_limit",
            "submission_type",
            "tutorial_pdf",
            "tutorial_video_url",
            "youtube_video_url",
            "loom_video_url",
            "external_links",
            "google_form_link",
            "google_sheet_link",
            "documentation_url",
            "instruction_file",
            "field_schema",
            "payment_settings",
            "limit_rules",
            "submission_rules",
            "metadata",
            "banner_image",
            "thumbnail",
            "application_deadline",
            "starts_at",
            "ends_at",
            "estimated_duration_minutes",
            "response_sla_hours",
            "is_private",
            "is_archived",
        ]


class SavedJobSerializer(serializers.ModelSerializer):
    job = JobPostingSerializer(read_only=True)

    class Meta:
        model = SavedJob
        fields = ["id", "job", "created_at"]


class JobFollowSerializer(serializers.ModelSerializer):
    job = JobPostingSerializer(read_only=True)

    class Meta:
        model = JobFollow
        fields = ["id", "job", "created_at"]


class RecruiterFollowSerializer(serializers.ModelSerializer):
    recruiter = CompactUserSerializer(read_only=True)

    class Meta:
        model = RecruiterFollow
        fields = ["id", "recruiter", "created_at"]


class DynamicSettingSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = DynamicSetting
        fields = [
            "id",
            "group",
            "key",
            "label",
            "value_type",
            "text_value",
            "number_value",
            "bool_value",
            "json_value",
            "default_text",
            "default_json",
            "description",
            "is_public",
            "is_editable",
            "metadata",
            "value",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["value", "created_at", "updated_at"]

    def get_value(self, obj):
        return obj.value


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "slug", "channel", "subject", "body", "variables", "is_active", "metadata"]


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsSnapshot
        fields = ["id", "snapshot_date", "scope", "payload", "source", "created_at", "updated_at"]

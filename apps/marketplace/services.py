"""Marketplace domain services."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.marketplace.models import (
    DynamicSetting,
    JobApplication,
    JobFollow,
    JobPosting,
    JobSubmission,
    MarketplaceProfile,
    RecruiterFollow,
    SavedJob,
)


class MarketplaceService:
    """Workflow operations for jobs, applications, follows, and settings."""

    @staticmethod
    def get_or_create_profile(user):
        profile, _ = MarketplaceProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def require_recruiter(user):
        profile = MarketplaceService.get_or_create_profile(user)
        if not (user.is_staff or profile.role in {"recruiter", "both"}):
            raise PermissionDenied("Recruiter access required.")
        return profile

    @staticmethod
    @transaction.atomic
    def create_or_update_job(user, validated_data, instance=None):
        MarketplaceService.require_recruiter(user)
        if instance is None:
            instance = JobPosting(recruiter=user)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.recruiter = user
        instance.save()
        return instance

    @staticmethod
    @transaction.atomic
    def apply_to_job(user, job, cover_letter="", expected_rate=None, payload=None):
        profile = MarketplaceService.get_or_create_profile(user)
        if profile.role not in {"worker", "both"} and not user.is_staff:
            raise PermissionDenied("Worker access required.")
        if not job.is_open:
            raise ValidationError("This job is not open for applications.")
        expected_rate_value = None
        if expected_rate not in {None, ""}:
            expected_rate_value = Decimal(str(expected_rate))
        application, created = JobApplication.objects.get_or_create(
            job=job,
            applicant=user,
            defaults={
                "cover_letter": cover_letter,
                "expected_rate": expected_rate_value,
                "workflow_payload": payload or {},
            },
        )
        if not created:
            application.cover_letter = cover_letter or application.cover_letter
            if expected_rate_value is not None:
                application.expected_rate = expected_rate_value
            application.workflow_payload = payload or application.workflow_payload
            application.status = "applied"
            application.applied_at = timezone.now()
            application.save()
        if created:
            MarketplaceService.award_xp(user, 5)
        return application

    @staticmethod
    @transaction.atomic
    def submit_application(user, application, submission_data):
        if application.applicant_id != user.id and not user.is_staff:
            raise PermissionDenied("You cannot submit work for this application.")
        payment_amount = submission_data.get("payment_amount", 0)
        payment_amount = Decimal(str(payment_amount)) if payment_amount not in {None, ""} else Decimal("0")
        submission = JobSubmission.objects.create(
            application=application,
            submitted_by=user,
            submission_type=submission_data["submission_type"],
            text_content=submission_data.get("text_content", ""),
            external_url=submission_data.get("external_url", ""),
            form_payload=submission_data.get("form_payload", {}),
            file_upload=submission_data.get("file_upload"),
            audio_upload=submission_data.get("audio_upload"),
            video_upload=submission_data.get("video_upload"),
            image_upload=submission_data.get("image_upload"),
            payment_amount=payment_amount,
        )
        application.status = "submitted"
        application.submitted_at = timezone.now()
        application.submission_note = submission_data.get("submission_note", application.submission_note)
        application.save(update_fields=["status", "submitted_at", "submission_note", "updated_at"])
        MarketplaceService.award_xp(user, 10)
        return submission

    @staticmethod
    @transaction.atomic
    def toggle_saved_job(user, job):
        saved, created = SavedJob.objects.get_or_create(user=user, job=job)
        if not created:
            saved.delete()
            return False
        return True

    @staticmethod
    @transaction.atomic
    def toggle_job_follow(user, job):
        follow, created = JobFollow.objects.get_or_create(user=user, job=job)
        if not created:
            follow.delete()
            return False
        return True

    @staticmethod
    @transaction.atomic
    def toggle_recruiter_follow(user, recruiter):
        follow, created = RecruiterFollow.objects.get_or_create(user=user, recruiter=recruiter)
        if not created:
            follow.delete()
            return False
        return True

    @staticmethod
    def get_setting(key, default=None):
        try:
            return DynamicSetting.objects.get(key=key).value
        except DynamicSetting.DoesNotExist:
            return default

    @staticmethod
    def award_xp(user, points):
        profile = MarketplaceService.get_or_create_profile(user)
        profile.add_xp(points)
        return profile

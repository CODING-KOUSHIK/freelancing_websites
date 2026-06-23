"""Data access helpers for marketplace workflows."""
from django.db.models import Count, Q, Sum
from django.contrib.auth import get_user_model

from apps.marketplace.models import (
    AnalyticsSnapshot,
    DynamicSetting,
    JobApplication,
    JobFollow,
    JobPosting,
    MarketplaceCategory,
    MarketplaceProfile,
    RecruiterFollow,
    SavedJob,
)

User = get_user_model()


class MarketplaceRepository:
    """Centralized read queries for portal and APIs."""

    def public_jobs(self):
        return (
            JobPosting.objects.select_related("recruiter", "category")
            .prefetch_related("media", "applications")
            .filter(status="published", is_archived=False)
            .order_by("-featured_job", "-created_at")
        )

    def job_detail_queryset(self):
        return JobPosting.objects.select_related("recruiter", "category").prefetch_related(
            "media",
            "applications__submissions",
        )

    def categories(self):
        return MarketplaceCategory.objects.filter(is_active=True).order_by("sort_order", "name")

    def portal_metrics(self):
        from django.utils import timezone
        from apps.accounts.models import CustomUser
        from apps.notifications.models import Notification
        from apps.presence.models import UserPresence
        from apps.recordings.models import RecordingSession
        from apps.support.models import SupportTicket
        from apps.wallet.models import Transaction, Withdrawal, Wallet

        today = timezone.now().date()
        week_start = today - timezone.timedelta(days=7)

        user_base = CustomUser.objects.all()
        active_users = user_base.filter(is_active=True).count()
        online_users = UserPresence.objects.filter(is_online=True).count()
        new_registrations = user_base.filter(date_joined__date=today).count()
        earnings = Wallet.objects.aggregate(total=Sum("total_earned"))["total"] or 0
        revenue = Transaction.objects.filter(transaction_type__in=["adjustment", "bonus", "recharge"]).aggregate(
            total=Sum("amount")
        )["total"] or 0
        pending_withdrawals = Withdrawal.objects.filter(status__in=["pending", "under_review"]).count()
        completed_withdrawals = Withdrawal.objects.filter(status="paid").aggregate(total=Sum("amount"))["total"] or 0
        open_tickets = SupportTicket.objects.filter(status__in=["open", "in_progress", "waiting_user"]).count()
        completed_tasks = JobApplication.objects.filter(status="completed").count()
        recording_hours = RecordingSession.objects.filter(status="completed").aggregate(
            total=Sum("duration_seconds")
        )["total"] or 0
        top_earners = (
            Wallet.objects.select_related("user")
            .order_by("-total_earned")[:10]
        )
        top_recruiters = (
            JobPosting.objects.filter(status="published")
            .values("recruiter__id", "recruiter__full_name", "recruiter__email")
            .annotate(
                jobs=Count("id", distinct=True),
                applications=Count("applications", distinct=True),
                completed=Count("applications", filter=Q(applications__status="completed"), distinct=True),
            )
            .order_by("-completed", "-jobs")[:10]
        )
        top_categories = (
            MarketplaceCategory.objects.annotate(
                jobs=Count("jobs", distinct=True),
                applications=Count("jobs__applications", distinct=True),
            )
            .order_by("-applications", "-jobs")[:10]
        )
        recent_jobs = self.public_jobs()[:8]
        recent_tickets = (
            SupportTicket.objects.select_related("user", "assigned_to")
            .order_by("-created_at")[:8]
        )
        recent_notifications = Notification.objects.order_by("-created_at")[:8]
        active_recordings = RecordingSession.objects.filter(status="in_progress").count()

        return {
            "total_users": user_base.count(),
            "active_users": active_users,
            "online_users": online_users,
            "new_registrations": new_registrations,
            "earnings": str(earnings),
            "revenue": str(revenue),
            "pending_withdrawals": pending_withdrawals,
            "completed_withdrawals": str(completed_withdrawals),
            "open_tickets": open_tickets,
            "completed_tasks": completed_tasks,
            "voice_recording_hours": round(recording_hours / 3600, 2),
            "top_earners": [
                {
                    "id": str(item.user_id),
                    "name": item.user.full_name,
                    "email": item.user.email,
                    "balance": str(item.total_earned),
                    "available_balance": str(item.available_balance),
                }
                for item in top_earners
            ],
            "top_recruiters": [
                {
                    "id": str(item["recruiter__id"]),
                    "name": item["recruiter__full_name"],
                    "email": item["recruiter__email"],
                    "jobs": item["jobs"],
                    "applications": item["applications"],
                    "completed": item["completed"],
                }
                for item in top_recruiters
            ],
            "top_categories": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "code": item.code,
                    "jobs": item.jobs,
                    "applications": item.applications,
                }
                for item in top_categories
            ],
            "recent_jobs": [
                {
                    "job_id": job.job_id,
                    "title": job.title,
                    "status": job.status,
                    "featured_job": job.featured_job,
                    "category": job.category.name,
                    "created_at": job.created_at.isoformat(),
                }
                for job in recent_jobs
            ],
            "recent_tickets": [
                {
                    "ticket_number": ticket.ticket_number,
                    "title": ticket.title,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "assigned_to": ticket.assigned_to.full_name if ticket.assigned_to else None,
                    "updated_at": ticket.updated_at.isoformat(),
                }
                for ticket in recent_tickets
            ],
            "recent_notifications": [
                {
                    "title": notification.title,
                    "message": notification.message,
                    "created_at": notification.created_at.isoformat(),
                    "is_read": notification.is_read,
                }
                for notification in recent_notifications
            ],
            "active_recordings": active_recordings,
            "settings_groups": DynamicSetting.objects.values("group").distinct().count(),
            "snapshot_count": AnalyticsSnapshot.objects.count(),
            "last_snapshot": AnalyticsSnapshot.objects.order_by("-snapshot_date").first().snapshot_date.isoformat()
            if AnalyticsSnapshot.objects.exists()
            else None,
        }

    def user_overview(self, user):
        return {
            "saved_jobs": SavedJob.objects.filter(user=user).count(),
            "followed_jobs": JobFollow.objects.filter(user=user).count(),
            "followed_recruiters": RecruiterFollow.objects.filter(user=user).count(),
            "applications": JobApplication.objects.filter(applicant=user).count(),
            "open_applications": JobApplication.objects.filter(
                applicant=user,
                status__in=["applied", "under_review", "approved", "assigned", "submitted", "verification"],
            ).count(),
        }

"""Core API views — Admin dashboard statistics"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from apps.recordings.models import RecordingSession
        from apps.wallet.models import Withdrawal, Wallet
        from apps.support.models import SupportTicket
        from apps.presence.models import UserPresence
        from apps.marketplace.models import JobPosting, JobSubmission, FixedTask

        User = get_user_model()
        now = timezone.now()
        today = now.date()
        last_30 = now - timedelta(days=30)
        last_7 = now - timedelta(days=7)

        # ─── User Metrics ───────────────────────────────────────
        total_users = User.objects.filter(is_active=True).count()
        online_users = UserPresence.objects.filter(is_online=True).count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_30d = User.objects.filter(date_joined__gte=last_30).count()

        # ─── Job Metrics ────────────────────────────────────────
        total_jobs = JobPosting.objects.count()
        active_jobs = JobPosting.objects.filter(status="published").count()
        trending_jobs = JobPosting.objects.filter(is_trending=True, status="published").count()
        draft_jobs = JobPosting.objects.filter(status="draft").count()

        # ─── Review Metrics ─────────────────────────────────────
        pending_reviews = JobSubmission.objects.filter(verification_status="pending").count()
        approved_reviews = JobSubmission.objects.filter(verification_status="approved").count()
        rejected_reviews = JobSubmission.objects.filter(verification_status="rejected").count()

        # ─── Recording Metrics ──────────────────────────────────
        total_recordings = RecordingSession.objects.filter(status="completed").count()
        recordings_today = RecordingSession.objects.filter(
            status="completed", ended_at__date=today
        ).count()
        total_seconds = RecordingSession.objects.filter(
            status="completed"
        ).aggregate(t=Sum("duration_seconds"))["t"] or 0
        pending_uploads = RecordingSession.objects.filter(upload_status="pending").count()

        # ─── Wallet / Revenue Metrics ───────────────────────────
        total_revenue = Wallet.objects.aggregate(t=Sum("total_earned"))["t"] or 0
        pending_withdrawals = Withdrawal.objects.filter(status="pending").count()
        total_withdrawn = Withdrawal.objects.filter(status="paid").aggregate(
            t=Sum("amount")
        )["t"] or 0
        withdrawal_volume_30d = Withdrawal.objects.filter(
            status="paid", created_at__gte=last_30
        ).aggregate(t=Sum("amount"))["t"] or 0

        # ─── Support Metrics ────────────────────────────────────
        open_tickets = SupportTicket.objects.filter(status="open").count()
        in_progress_tickets = SupportTicket.objects.filter(status="in_progress").count()
        pending_tickets = open_tickets + in_progress_tickets

        # ─── Fixed Task Metrics ─────────────────────────────────
        pending_tasks = FixedTask.objects.filter(status__in=["pending", "assigned"]).count()
        submitted_tasks = FixedTask.objects.filter(status="submitted").count()

        # ─── Daily chart data (last 7 days) ─────────────────────
        daily_uploads = []
        daily_earnings = []
        user_growth = []

        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_label = day.strftime("%a")

            uploads = RecordingSession.objects.filter(
                status="completed", ended_at__date=day
            ).count()

            earnings = JobSubmission.objects.filter(
                verification_status="approved",
                verified_at__date=day,
            ).aggregate(t=Sum("payment_amount"))["t"] or 0

            new_user_count = User.objects.filter(date_joined__date=day).count()

            daily_uploads.append({"day": day_label, "count": uploads})
            daily_earnings.append({"day": day_label, "amount": float(earnings)})
            user_growth.append({"day": day_label, "count": new_user_count})

        return Response({
            # Users
            "total_users": total_users,
            "online_users": online_users,
            "new_users_today": new_users_today,
            "new_users_30d": new_users_30d,

            # Jobs
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "trending_jobs": trending_jobs,
            "draft_jobs": draft_jobs,

            # Reviews
            "pending_reviews": pending_reviews,
            "approved_reviews": approved_reviews,
            "rejected_reviews": rejected_reviews,

            # Recordings
            "total_recordings": total_recordings,
            "recordings_today": recordings_today,
            "total_hours": round(total_seconds / 3600, 2),
            "pending_uploads": pending_uploads,

            # Revenue
            "total_revenue": str(total_revenue),
            "pending_withdrawals": pending_withdrawals,
            "total_withdrawn": str(total_withdrawn),
            "withdrawal_volume_30d": str(withdrawal_volume_30d),

            # Support
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "pending_tickets": pending_tickets,

            # Tasks
            "pending_tasks": pending_tasks,
            "submitted_tasks": submitted_tasks,

            # Charts
            "daily_uploads": daily_uploads,
            "daily_earnings": daily_earnings,
            "user_growth": user_growth,
        })

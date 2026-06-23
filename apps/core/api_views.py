"""Core API views — Admin dashboard statistics"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        from apps.recordings.models import RecordingSession
        from apps.wallet.models import Withdrawal, Wallet
        from apps.support.models import SupportTicket
        from apps.presence.models import UserPresence
        from django.db.models import Sum

        User = get_user_model()

        total_users = User.objects.filter(is_active=True).count()
        online_users = UserPresence.objects.filter(is_online=True).count()
        total_recordings = RecordingSession.objects.filter(status="completed").count()
        total_seconds = RecordingSession.objects.filter(
            status="completed"
        ).aggregate(t=Sum("duration_seconds"))["t"] or 0

        total_revenue = Wallet.objects.aggregate(t=Sum("total_earned"))["t"] or 0
        pending_withdrawals = Withdrawal.objects.filter(status="pending").count()
        total_withdrawn = Withdrawal.objects.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
        pending_tickets = SupportTicket.objects.filter(status__in=["open", "in_progress"]).count()

        return Response({
            "total_users": total_users,
            "online_users": online_users,
            "total_recordings": total_recordings,
            "total_hours": round(total_seconds / 3600, 2),
            "total_revenue": str(total_revenue),
            "pending_withdrawals": pending_withdrawals,
            "total_withdrawn": str(total_withdrawn),
            "pending_tickets": pending_tickets,
        })

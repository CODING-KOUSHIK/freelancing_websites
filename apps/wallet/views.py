"""Wallet API views"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from apps.wallet.models import (
    EarningRate,
    RechargeOperator,
    RechargeOrder,
    RechargePlan,
    Transaction,
    Wallet,
    Withdrawal,
)
from apps.wallet.serializers import (
    EarningRateSerializer,
    RechargeOperatorSerializer,
    RechargeOperatorWriteSerializer,
    RechargeOrderCreateSerializer,
    RechargeOrderSerializer,
    RechargePlanSerializer,
    RechargePlanWriteSerializer,
    TransactionSerializer,
    WalletSerializer,
    WithdrawalSerializer,
)
from apps.notifications.models import Notification
from apps.core.models import AuditLog


class WalletView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["transaction_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet.transactions.all()


class WithdrawalListCreateView(generics.ListCreateAPIView):
    serializer_class = WithdrawalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        amount = serializer.validated_data["amount"]
        wallet = user.wallet

        # Debit immediately to reserve funds
        wallet.debit(
            amount=amount,
            description=f"Withdrawal request",
        )

        withdrawal = serializer.save(user=user)

        AuditLog.objects.create(
            user=user, action="withdrawal_request",
            description=f"Withdrawal request for ₹{amount} via {withdrawal.method}",
        )

        Notification.send(
            user=user,
            notification_type="system",
            title="Withdrawal Request Submitted",
            message=f"Your withdrawal request for ₹{amount} has been submitted and is under review.",
            action_url="/wallet/withdrawals/",
        )


class WithdrawalDetailView(generics.RetrieveAPIView):
    serializer_class = WithdrawalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Withdrawal.objects.filter(user=self.request.user)


class EarningRateListView(generics.ListAPIView):
    serializer_class = EarningRateSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = EarningRate.objects.filter(is_active=True)


class EarningsSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.recordings.models import RecordingSession
        from django.db.models import Q, Sum
        user = request.user
        sessions = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user),
            status="completed",
            earnings_calculated=True,
        )

        # Monthly breakdown
        from django.db.models.functions import TruncMonth
        monthly = (
            sessions
            .annotate(month=TruncMonth("ended_at"))
            .values("month")
            .annotate(total=Sum("earnings_amount"))
            .order_by("-month")[:12]
        )

        return Response({
            "total_sessions": sessions.count(),
            "total_earned": str(user.wallet.total_earned if hasattr(user, "wallet") else 0),
            "monthly_breakdown": [
                {
                    "month": item["month"].strftime("%B %Y") if item["month"] else "",
                    "total": str(item["total"] or 0),
                }
                for item in monthly
            ],
        })


class RechargeOperatorListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = RechargeOperator.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RechargeOperatorWriteSerializer
        return RechargeOperatorSerializer


class RechargeOperatorDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = RechargeOperator.objects.all()

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return RechargeOperatorWriteSerializer
        return RechargeOperatorSerializer


class RechargePlanListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = RechargePlan.objects.select_related("operator").all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RechargePlanWriteSerializer
        return RechargePlanSerializer


class RechargePlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = RechargePlan.objects.select_related("operator").all()

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return RechargePlanWriteSerializer
        return RechargePlanSerializer


class RechargeOrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RechargeOrderSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return RechargeOrder.objects.select_related("user", "operator", "plan")
        return RechargeOrder.objects.filter(user=self.request.user).select_related("user", "operator", "plan")


class RechargeOrderCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RechargeOrderCreateSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status="pending")

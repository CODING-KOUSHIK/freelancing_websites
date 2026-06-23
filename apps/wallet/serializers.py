"""Wallet serializers"""
from rest_framework import serializers

from apps.wallet.models import (
    EarningRate,
    RechargeOperator,
    RechargeOrder,
    RechargePlan,
    Transaction,
    Wallet,
    Withdrawal,
)


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            "available_balance", "pending_balance",
            "processing_balance", "bonus_balance", "referral_balance",
            "total_earned", "lifetime_earnings", "total_withdrawn", "currency", "is_frozen",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id", "transaction_type", "amount", "balance_after",
            "description", "reference", "created_at",
        ]


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "id", "amount", "method", "status",
            "bank_name", "account_number", "ifsc_code",
            "account_holder_name", "upi_id",
            "admin_note", "created_at", "processed_at",
        ]
        read_only_fields = ["status", "admin_note", "created_at", "processed_at"]

    def validate_amount(self, value):
        user = self.context["request"].user
        try:
            wallet = user.wallet
        except Exception:
            raise serializers.ValidationError("Wallet not found.")
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        if wallet.available_balance < value:
            raise serializers.ValidationError("Insufficient balance.")
        min_withdrawal = 100
        if value < min_withdrawal:
            raise serializers.ValidationError(f"Minimum withdrawal is ₹{min_withdrawal}.")
        return value


class EarningRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarningRate
        fields = ["category", "per_minute_rate", "per_hour_rate", "bonus_multiplier"]


class RechargeOperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeOperator
        fields = ["id", "name", "code", "is_active", "sort_order", "metadata", "created_at"]


class RechargeOperatorWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeOperator
        fields = ["id", "name", "code", "is_active", "sort_order", "metadata"]
        read_only_fields = ["id"]


class RechargePlanSerializer(serializers.ModelSerializer):
    operator = RechargeOperatorSerializer(read_only=True)

    class Meta:
        model = RechargePlan
        fields = [
            "id",
            "operator",
            "circle",
            "plan_name",
            "amount",
            "validity_days",
            "data_allowance",
            "talktime",
            "cashback_amount",
            "commission_amount",
            "external_plan_id",
            "payload",
            "is_active",
            "sort_order",
            "created_at",
        ]


class RechargePlanWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargePlan
        fields = [
            "id",
            "operator",
            "circle",
            "plan_name",
            "amount",
            "validity_days",
            "data_allowance",
            "talktime",
            "cashback_amount",
            "commission_amount",
            "external_plan_id",
            "payload",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id"]


class RechargeOrderSerializer(serializers.ModelSerializer):
    operator = RechargeOperatorSerializer(read_only=True)
    plan = RechargePlanSerializer(read_only=True)

    class Meta:
        model = RechargeOrder
        fields = [
            "id",
            "user",
            "operator",
            "plan",
            "mobile_number",
            "status",
            "amount",
            "cashback_amount",
            "commission_amount",
            "transaction_ref",
            "payload",
            "processed_by",
            "processed_at",
            "created_at",
        ]
        read_only_fields = ["user", "status", "transaction_ref", "processed_by", "processed_at", "created_at"]


class RechargeOrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeOrder
        fields = ["operator", "plan", "mobile_number", "amount", "payload"]

    def validate(self, attrs):
        plan = attrs.get("plan")
        if plan and not attrs.get("amount"):
            attrs["amount"] = plan.amount
        return attrs

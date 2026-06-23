"""Wallet admin"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.wallet.models import Wallet, Transaction, Withdrawal, EarningRate, BonusCampaign
from apps.notifications.models import Notification


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "available_balance", "pending_balance", "total_earned", "is_frozen"]
    search_fields = ["user__email", "user__full_name"]
    list_filter = ["is_frozen", "currency"]
    readonly_fields = ["total_earned", "total_withdrawn"]

    actions = ["freeze_wallets", "unfreeze_wallets"]

    def freeze_wallets(self, request, queryset):
        queryset.update(is_frozen=True)
    freeze_wallets.short_description = "Freeze selected wallets"

    def unfreeze_wallets(self, request, queryset):
        queryset.update(is_frozen=False)
    unfreeze_wallets.short_description = "Unfreeze selected wallets"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["wallet", "transaction_type", "amount", "balance_after", "description", "created_at"]
    list_filter = ["transaction_type"]
    search_fields = ["wallet__user__email", "reference"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = [
        "user", "amount", "method", "status_badge",
        "processed_by", "created_at",
    ]
    list_filter = ["status", "method"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["user", "amount", "method", "created_at"]
    ordering = ["-created_at"]
    actions = ["approve_withdrawals", "reject_withdrawals", "mark_paid"]

    def status_badge(self, obj):
        colors = {
            "pending": "orange", "approved": "blue",
            "paid": "green", "rejected": "red", "failed": "darkred",
        }
        color = colors.get(obj.status, "gray")
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def approve_withdrawals(self, request, queryset):
        for w in queryset.filter(status="pending"):
            w.status = "approved"
            w.processed_by = request.user
            w.processed_at = timezone.now()
            w.save()
            Notification.send(
                user=w.user, notification_type="withdrawal_approved",
                title="Withdrawal Approved ✅",
                message=f"Your withdrawal of ₹{w.amount} has been approved.",
                action_url="/wallet/",
            )
        self.message_user(request, "Selected withdrawals approved.")
    approve_withdrawals.short_description = "Approve withdrawals"

    def reject_withdrawals(self, request, queryset):
        for w in queryset.filter(status__in=["pending", "approved"]):
            # Refund the amount
            try:
                w.user.wallet.credit(
                    amount=w.amount,
                    description=f"Withdrawal rejected — refund",
                    transaction_type="adjustment",
                )
            except Exception:
                pass
            w.status = "rejected"
            w.processed_by = request.user
            w.processed_at = timezone.now()
            w.save()
            Notification.send(
                user=w.user, notification_type="withdrawal_rejected",
                title="Withdrawal Rejected",
                message=f"Your withdrawal of ₹{w.amount} was rejected. Amount refunded.",
                action_url="/wallet/",
            )
    reject_withdrawals.short_description = "Reject withdrawals (with refund)"

    def mark_paid(self, request, queryset):
        for w in queryset.filter(status="approved"):
            w.status = "paid"
            w.processed_at = timezone.now()
            w.save()
            Notification.send(
                user=w.user, notification_type="withdrawal_paid",
                title="Payment Sent 💸",
                message=f"₹{w.amount} has been transferred to your account.",
                action_url="/wallet/",
            )
    mark_paid.short_description = "Mark as paid"


@admin.register(EarningRate)
class EarningRateAdmin(admin.ModelAdmin):
    list_display = ["category", "per_minute_rate", "per_hour_rate", "bonus_multiplier", "is_active"]
    list_editable = ["per_minute_rate", "per_hour_rate", "is_active"]


@admin.register(BonusCampaign)
class BonusCampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "condition_type", "reward_amount", "start_date", "end_date", "is_active"]
    list_editable = ["is_active"]

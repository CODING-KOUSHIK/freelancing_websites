"""Wallet admin — Wallet, Transactions, Withdrawals with full management."""
import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone

from apps.wallet.models import (
    Wallet, Transaction, Withdrawal, EarningRate,
    BonusCampaign, RechargeOperator, RechargePlan, RechargeOrder,
)
from apps.notifications.models import Notification


# ──────────────────────────────────────────────────────────────
# Wallet
# ──────────────────────────────────────────────────────────────

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        "user", "available_balance_display", "pending_balance_display",
        "total_earned", "total_withdrawn", "is_frozen",
    ]
    search_fields = ["user__email", "user__full_name"]
    list_filter = ["is_frozen", "currency"]
    readonly_fields = ["total_earned", "lifetime_earnings", "total_withdrawn", "updated_at"]
    list_per_page = 40

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Balances", {
            "fields": ("available_balance", "pending_balance", "processing_balance",
                       "bonus_balance", "referral_balance"),
        }),
        ("Totals (Read-only)", {
            "fields": ("total_earned", "lifetime_earnings", "total_withdrawn"),
        }),
        ("Settings", {"fields": ("currency", "is_frozen", "updated_at")}),
    )

    actions = ["freeze_wallets", "unfreeze_wallets", "export_wallets_csv"]

    def available_balance_display(self, obj):
        color = "#4ade80" if obj.available_balance > 0 else "#9ca3af"
        return format_html('<span style="color:{};font-weight:600;">₹{}</span>', color, obj.available_balance)
    available_balance_display.short_description = "Available"

    def pending_balance_display(self, obj):
        color = "#fb923c" if obj.pending_balance > 0 else "#9ca3af"
        return format_html('<span style="color:{};">₹{}</span>', color, obj.pending_balance)
    pending_balance_display.short_description = "Pending"

    def freeze_wallets(self, request, queryset):
        queryset.update(is_frozen=True)
        self.message_user(request, "🔒 Selected wallets frozen.")
    freeze_wallets.short_description = "Freeze selected wallets"

    def unfreeze_wallets(self, request, queryset):
        queryset.update(is_frozen=False)
        self.message_user(request, "🔓 Selected wallets unfrozen.")
    unfreeze_wallets.short_description = "Unfreeze selected wallets"

    def export_wallets_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="wallets_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["Email", "Name", "Available", "Pending", "Total Earned", "Total Withdrawn", "Frozen"])
        for w in queryset.select_related("user"):
            writer.writerow([
                w.user.email, w.user.full_name,
                w.available_balance, w.pending_balance,
                w.total_earned, w.total_withdrawn, w.is_frozen,
            ])
        return response
    export_wallets_csv.short_description = "Export to CSV"


# ──────────────────────────────────────────────────────────────
# Transaction
# ──────────────────────────────────────────────────────────────

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id_short", "wallet", "type_badge", "amount_display",
        "balance_after", "description", "created_at",
    ]
    list_filter = ["transaction_type"]
    search_fields = ["wallet__user__email", "reference", "description"]
    readonly_fields = ["created_at", "id"]
    ordering = ["-created_at"]
    list_per_page = 50

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "TXN"

    def type_badge(self, obj):
        colors = {
            "credit": "#4ade80", "debit": "#f87171", "pending": "#fb923c",
            "processing": "#60a5fa", "recording_income": "#a78bfa",
            "task_income": "#34d399", "bonus": "#fbbf24",
            "referral": "#f472b6", "withdrawal": "#f87171",
            "refund": "#60a5fa", "adjustment": "#9ca3af",
        }
        color = colors.get(obj.transaction_type, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_transaction_type_display())
    type_badge.short_description = "Type"

    def amount_display(self, obj):
        color = "#4ade80" if obj.transaction_type == "credit" else "#f87171"
        prefix = "+" if obj.transaction_type in ("credit", "bonus", "referral") else "-"
        return format_html('<span style="color:{};font-weight:600;">{}{}</span>', color, prefix, obj.amount)
    amount_display.short_description = "Amount"


# ──────────────────────────────────────────────────────────────
# Withdrawal
# ──────────────────────────────────────────────────────────────

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = [
        "user", "amount_display", "method", "status_badge",
        "processed_by", "created_at",
    ]
    list_filter = ["status", "method"]
    search_fields = ["user__email", "user__full_name", "upi_id", "account_number"]
    # ✅ FIXED: Only created_at is readonly — admin_note and status are fully editable
    readonly_fields = ["user", "created_at", "processed_at"]
    ordering = ["-created_at"]
    list_per_page = 40
    date_hierarchy = "created_at"
    save_on_top = True

    fieldsets = (
        ("Request", {
            "fields": ("user", "amount", "method", "status", "created_at"),
        }),
        ("Bank / UPI Details", {
            "fields": ("bank_name", "account_number", "ifsc_code",
                       "account_holder_name", "upi_id"),
        }),
        ("Processing", {
            "fields": ("admin_note", "processed_by", "processed_at", "transaction_ref"),
        }),
    )

    actions = [
        "approve_withdrawals", "reject_withdrawals",
        "mark_processing", "mark_paid", "export_withdrawals_csv",
    ]

    def status_badge(self, obj):
        colors = {
            "pending": "#fb923c", "under_review": "#60a5fa",
            "approved": "#4ade80", "rejected": "#f87171",
            "paid": "#22c55e", "failed": "#dc2626",
        }
        color = colors.get(obj.status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:700;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def amount_display(self, obj):
        return format_html('<span style="color:#4ade80;font-weight:600;">₹{}</span>', obj.amount)
    amount_display.short_description = "Amount"

    def approve_withdrawals(self, request, queryset):
        now = timezone.now()
        count = 0
        for w in queryset.filter(status="pending"):
            w.status = "approved"
            w.processed_by = request.user
            w.processed_at = now
            w.save(update_fields=["status", "processed_by", "processed_at"])
            Notification.send(
                user=w.user,
                notification_type="withdrawal_approved",
                title="Withdrawal Approved ✅",
                message=f"Your withdrawal of ₹{w.amount} has been approved and is being processed.",
                action_url="/wallet/",
            )
            count += 1
        self.message_user(request, f"✅ {count} withdrawal(s) approved.")
    approve_withdrawals.short_description = "✅ Approve withdrawals"

    def reject_withdrawals(self, request, queryset):
        now = timezone.now()
        count = 0
        for w in queryset.filter(status__in=["pending", "approved", "under_review"]):
            # Refund the amount back to the wallet
            try:
                w.user.wallet.credit(
                    amount=w.amount,
                    description=f"Withdrawal refund — request rejected",
                    transaction_type="adjustment",
                )
            except Exception:
                pass
            w.status = "rejected"
            w.processed_by = request.user
            w.processed_at = now
            w.save(update_fields=["status", "processed_by", "processed_at"])
            Notification.send(
                user=w.user,
                notification_type="withdrawal_rejected",
                title="Withdrawal Rejected",
                message=f"Your withdrawal of ₹{w.amount} was rejected. Amount refunded to wallet.",
                action_url="/wallet/",
            )
            count += 1
        self.message_user(request, f"❌ {count} withdrawal(s) rejected and refunded.")
    reject_withdrawals.short_description = "❌ Reject withdrawals (with refund)"

    def mark_processing(self, request, queryset):
        now = timezone.now()
        count = queryset.filter(status="approved").update(
            status="under_review", processed_by=request.user, processed_at=now
        )
        self.message_user(request, f"🔄 {count} withdrawal(s) moved to Under Review.")
    mark_processing.short_description = "Move to Under Review"

    def mark_paid(self, request, queryset):
        now = timezone.now()
        count = 0
        for w in queryset.filter(status="approved"):
            w.status = "paid"
            w.processed_at = now
            w.save(update_fields=["status", "processed_at"])
            Notification.send(
                user=w.user,
                notification_type="withdrawal_paid",
                title="Payment Sent 💸",
                message=f"₹{w.amount} has been transferred to your account.",
                action_url="/wallet/",
            )
            count += 1
        self.message_user(request, f"💸 {count} withdrawal(s) marked as Paid.")
    mark_paid.short_description = "💸 Mark as Paid"

    def export_withdrawals_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="withdrawals_export.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "ID", "User Email", "User Name", "Amount", "Method", "Status",
            "UPI ID", "Bank Name", "Account Number", "IFSC",
            "Admin Note", "Transaction Ref", "Created At", "Processed At",
        ])
        for w in queryset.select_related("user"):
            writer.writerow([
                str(w.id), w.user.email, w.user.full_name,
                w.amount, w.method, w.status,
                w.upi_id, w.bank_name, w.account_number, w.ifsc_code,
                w.admin_note, w.transaction_ref,
                w.created_at, w.processed_at,
            ])
        return response
    export_withdrawals_csv.short_description = "📥 Export to CSV"


# ──────────────────────────────────────────────────────────────
# EarningRate
# ──────────────────────────────────────────────────────────────

@admin.register(EarningRate)
class EarningRateAdmin(admin.ModelAdmin):
    list_display = ["category", "per_minute_rate", "per_hour_rate", "bonus_multiplier", "is_active"]
    list_editable = ["per_minute_rate", "per_hour_rate", "bonus_multiplier", "is_active"]


# ──────────────────────────────────────────────────────────────
# BonusCampaign
# ──────────────────────────────────────────────────────────────

@admin.register(BonusCampaign)
class BonusCampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "condition_type", "reward_amount", "start_date", "end_date", "is_active"]
    list_filter = ["condition_type", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["name"]


# ──────────────────────────────────────────────────────────────
# RechargeOperator / Plan / Order
# ──────────────────────────────────────────────────────────────

@admin.register(RechargeOperator)
class RechargeOperatorAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]


@admin.register(RechargePlan)
class RechargePlanAdmin(admin.ModelAdmin):
    list_display = ["operator", "plan_name", "amount", "validity_days", "cashback_amount", "is_active"]
    list_filter = ["operator", "is_active"]
    search_fields = ["plan_name"]
    list_editable = ["is_active"]


@admin.register(RechargeOrder)
class RechargeOrderAdmin(admin.ModelAdmin):
    list_display = ["user", "operator", "mobile_number", "amount", "status", "created_at"]
    list_filter = ["status", "operator"]
    search_fields = ["user__email", "mobile_number"]
    readonly_fields = ["created_at", "processed_at"]
    ordering = ["-created_at"]

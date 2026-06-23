"""Accounts admin — Full user management panel"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from apps.accounts.models import CustomUser, EmailOTP, LoginHistory, DeviceTracking, KYCDocument


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = [
        "email", "full_name", "level", "kyc_status",
        "is_verified", "is_suspended", "is_banned",
        "reputation_score", "online_status", "date_joined",
    ]
    list_filter = ["level", "kyc_status", "is_verified", "is_suspended", "is_banned", "gender", "country"]
    search_fields = ["email", "full_name", "whatsapp_number", "referral_code"]
    ordering = ["-date_joined"]
    readonly_fields = ["date_joined", "last_login", "referral_code", "reputation_score", "profile_completion_display"]

    fieldsets = (
        ("Account", {"fields": ("email", "password", "is_active", "is_staff", "is_superuser")}),
        ("Personal Info", {"fields": ("full_name", "gender", "date_of_birth", "country", "whatsapp_number", "profile_photo", "bio")}),
        ("Verification", {"fields": ("is_verified", "is_profile_verified", "kyc_status")}),
        ("Status", {"fields": ("is_suspended", "is_banned")}),
        ("Gamification", {"fields": ("level", "reputation_score", "login_streak", "referral_code", "referred_by")}),
        ("Settings", {"fields": ("dark_mode", "email_notifications", "whatsapp_notifications", "auto_accept_requests", "preferred_language")}),
        ("Timestamps", {"fields": ("date_joined", "last_login")}),
        ("Profile", {"fields": ("profile_completion_display",)}),
    )

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
    )

    def online_status(self, obj):
        try:
            if obj.presence.is_online:
                return format_html('<span style="color:green;">● Online</span>')
            return format_html('<span style="color:gray;">○ Offline</span>')
        except Exception:
            return "—"
    online_status.short_description = "Status"

    def profile_completion_display(self, obj):
        pct = obj.profile_completion
        color = "green" if pct >= 80 else "orange" if pct >= 50 else "red"
        return format_html(
            '<div style="width:200px;background:#eee;border-radius:4px;">'
            '<div style="width:{}%;background:{};height:16px;border-radius:4px;"></div>'
            '</div> {}%',
            pct, color, pct,
        )
    profile_completion_display.short_description = "Profile Completion"

    actions = ["suspend_users", "unsuspend_users", "ban_users", "verify_users", "approve_kyc"]

    def suspend_users(self, request, queryset):
        queryset.update(is_suspended=True)
        self.message_user(request, f"{queryset.count()} users suspended.")
    suspend_users.short_description = "Suspend selected users"

    def unsuspend_users(self, request, queryset):
        queryset.update(is_suspended=False)
    unsuspend_users.short_description = "Unsuspend selected users"

    def ban_users(self, request, queryset):
        queryset.update(is_banned=True, is_active=False)
    ban_users.short_description = "Ban selected users"

    def verify_users(self, request, queryset):
        queryset.update(is_profile_verified=True)
    verify_users.short_description = "Mark as profile verified"

    def approve_kyc(self, request, queryset):
        queryset.update(kyc_status="approved")
    approve_kyc.short_description = "Approve KYC"


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ["user", "otp_code", "purpose", "is_used", "expires_at", "created_at"]
    list_filter = ["purpose", "is_used"]
    search_fields = ["user__email"]
    readonly_fields = ["created_at"]


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ["user", "ip_address", "device_type", "success", "created_at"]
    list_filter = ["success", "device_type"]
    search_fields = ["user__email", "ip_address"]
    readonly_fields = ["created_at"]


@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ["user", "doc_type", "status", "created_at"]
    list_filter = ["status", "doc_type"]
    search_fields = ["user__email"]
    actions = ["approve_docs", "reject_docs"]

    def approve_docs(self, request, queryset):
        from apps.notifications.models import Notification
        for doc in queryset:
            doc.status = "approved"
            doc.reviewed_at = timezone.now()
            doc.reviewed_by = request.user
            doc.save()
            doc.user.kyc_status = "approved"
            doc.user.save(update_fields=["kyc_status"])
            Notification.send(
                user=doc.user, notification_type="kyc_approved",
                title="KYC Approved ✅",
                message="Your KYC documents have been approved.",
            )
        self.message_user(request, f"{queryset.count()} KYC documents approved.")
    approve_docs.short_description = "Approve selected KYC documents"

    def reject_docs(self, request, queryset):
        from apps.notifications.models import Notification
        for doc in queryset:
            doc.status = "rejected"
            doc.reviewed_at = timezone.now()
            doc.reviewed_by = request.user
            doc.save()
            doc.user.kyc_status = "rejected"
            doc.user.save(update_fields=["kyc_status"])
            Notification.send(
                user=doc.user, notification_type="kyc_rejected",
                title="KYC Rejected ❌",
                message="Your KYC documents were rejected. Please re-submit.",
            )
    reject_docs.short_description = "Reject selected KYC documents"

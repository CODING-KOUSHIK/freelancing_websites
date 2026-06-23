"""Core admin"""
from django.contrib import admin
from apps.core.models import SiteSettings, AuditLog, Achievement, UserAchievement, Referral, WeeklyChallenge


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["key", "value", "description", "updated_at"]
    search_fields = ["key"]
    ordering = ["key"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["user", "action", "ip_address", "description", "created_at"]
    list_filter = ["action"]
    search_fields = ["user__email", "ip_address", "description"]
    readonly_fields = ["id", "user", "action", "ip_address", "user_agent", "description", "extra_data", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ["name", "icon", "condition_type", "condition_value", "points", "is_active"]
    list_editable = ["is_active", "points"]


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ["user", "achievement", "earned_at"]
    search_fields = ["user__email"]


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ["referrer", "referred_user", "bonus_amount", "bonus_paid", "created_at"]
    list_filter = ["bonus_paid"]
    search_fields = ["referrer__email", "referred_user__email"]


@admin.register(WeeklyChallenge)
class WeeklyChallengeAdmin(admin.ModelAdmin):
    list_display = ["title", "goal_type", "goal_value", "reward_amount", "start_date", "end_date", "is_active"]
    list_editable = ["is_active"]

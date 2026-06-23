"""Notifications admin"""
from django.contrib import admin
from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "notification_type", "title", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["user__email", "title"]
    readonly_fields = ["created_at"]
    actions = ["mark_all_read"]

    def mark_all_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_all_read.short_description = "Mark as read"

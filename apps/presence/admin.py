"""Presence admin"""
from django.contrib import admin
from apps.presence.models import UserPresence


@admin.register(UserPresence)
class UserPresenceAdmin(admin.ModelAdmin):
    list_display = ["user", "is_online", "last_seen", "channel_name"]
    list_filter = ["is_online"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["last_seen"]

"""Ratings admin"""
from django.contrib import admin
from apps.ratings.models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["rater", "ratee", "score", "is_abuse_report", "abuse_reviewed", "created_at"]
    list_filter = ["score", "is_abuse_report", "abuse_reviewed"]
    search_fields = ["rater__email", "ratee__email"]
    readonly_fields = ["created_at"]
    actions = ["review_abuse_reports"]

    def review_abuse_reports(self, request, queryset):
        queryset.update(abuse_reviewed=True, abuse_reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} abuse reports marked as reviewed.")
    review_abuse_reports.short_description = "Mark abuse reports as reviewed"

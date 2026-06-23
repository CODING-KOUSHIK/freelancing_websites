"""Support admin"""
from django.contrib import admin
from django.utils import timezone
from apps.support.models import SupportTicket, TicketReply


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 1
    readonly_fields = ["created_at"]
    fields = ["author", "message", "attachment", "is_internal_note", "created_at"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_number", "user", "title", "category",
        "status", "priority", "assigned_to", "created_at",
    ]
    list_filter = ["status", "priority", "category"]
    search_fields = ["ticket_number", "user__email", "title"]
    readonly_fields = ["ticket_number", "created_at"]
    ordering = ["-created_at"]
    inlines = [TicketReplyInline]
    list_editable = ["status", "priority", "assigned_to"]

    actions = ["resolve_tickets", "close_tickets"]

    def resolve_tickets(self, request, queryset):
        for ticket in queryset:
            ticket.status = "resolved"
            ticket.resolved_at = timezone.now()
            ticket.save()
            from apps.notifications.models import Notification
            Notification.send(
                user=ticket.user, notification_type="ticket_resolved",
                title=f"Ticket #{ticket.ticket_number} Resolved",
                message="Your support ticket has been resolved.",
                action_url=f"/support/tickets/{ticket.pk}/",
            )
    resolve_tickets.short_description = "Mark as resolved"

    def close_tickets(self, request, queryset):
        queryset.update(status="closed")
    close_tickets.short_description = "Close selected tickets"


@admin.register(TicketReply)
class TicketReplyAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal_note", "created_at"]
    list_filter = ["is_internal_note"]
    readonly_fields = ["created_at"]

"""Support admin — Ticket management with auto-reply author and full lifecycle."""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.support.models import SupportTicket, TicketReply
from apps.notifications.models import Notification


class TicketReplyInline(admin.StackedInline):
    model = TicketReply
    extra = 1
    readonly_fields = ["author_display", "created_at"]
    fields = ["author_display", "message", "attachment", "is_internal_note", "created_at"]
    verbose_name = "Reply / Note"
    verbose_name_plural = "Replies & Internal Notes"

    def author_display(self, obj):
        if obj.pk:
            kind = "🔒 Internal Note" if obj.is_internal_note else "💬 Reply"
            return format_html("{} by <strong>{}</strong>", kind, obj.author.full_name)
        return "—"
    author_display.short_description = "Author"

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing existing ticket — author is set, keep readonly
            return ["author_display", "created_at"]
        return ["author_display", "created_at"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        "ticket_number", "user", "title", "category",
        "status_badge", "priority_badge", "assigned_to", "created_at",
    ]
    list_filter = ["status", "priority", "category"]
    search_fields = ["ticket_number", "user__email", "user__full_name", "title"]
    readonly_fields = [
        "ticket_number", "created_at", "first_response_at",
        "last_response_at", "resolved_at", "sla_due_at",
        "reply_count_display",
    ]
    ordering = ["-created_at"]
    inlines = [TicketReplyInline]
    list_per_page = 40
    date_hierarchy = "created_at"
    save_on_top = True

    fieldsets = (
        ("🎫 Ticket", {
            "fields": ("ticket_number", "user", "title", "description",
                       "category", "status", "priority", "assigned_to"),
        }),
        ("⏱ SLA & Timeline", {
            "fields": ("sla_due_at", "first_response_at", "last_response_at",
                       "resolved_at", "created_at"),
            "classes": ("collapse",),
        }),
        ("📊 Stats", {
            "fields": ("reply_count_display", "escalation_level"),
        }),
        ("⚙ Meta", {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "resolve_tickets", "close_tickets", "reopen_tickets",
        "assign_to_me", "mark_in_progress",
    ]

    def save_formset(self, request, form, formset, change):
        """Auto-set author on new TicketReply instances."""
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, TicketReply) and not obj.pk:
                obj.author = request.user
                obj.save()
                # Update ticket response timestamps
                ticket = obj.ticket
                now = timezone.now()
                updates = ["last_response_at"]
                ticket.last_response_at = now
                if not ticket.first_response_at:
                    ticket.first_response_at = now
                    updates.append("first_response_at")
                # Update status if staff is replying
                if request.user.is_staff and ticket.status == "open":
                    ticket.status = "in_progress"
                    updates.append("status")
                ticket.save(update_fields=updates)
                # Notify the ticket user (if admin is replying)
                if request.user.is_staff and not obj.is_internal_note:
                    Notification.send(
                        user=ticket.user,
                        notification_type="ticket_reply",
                        title=f"Reply on Ticket #{ticket.ticket_number}",
                        message=f"Support team replied to your ticket: {ticket.title}",
                        action_url=f"/support/tickets/{ticket.pk}/",
                    )
                # Notify assigned staff if user is replying
                elif not request.user.is_staff and ticket.assigned_to:
                    Notification.send(
                        user=ticket.assigned_to,
                        notification_type="ticket_reply",
                        title=f"New reply on #{ticket.ticket_number}",
                        message=f"{request.user.full_name} replied to the ticket.",
                        action_url=f"/admin/support/supportticket/{ticket.pk}/change/",
                    )
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()

    def status_badge(self, obj):
        colors = {
            "open": "#4ade80",
            "in_progress": "#60a5fa",
            "waiting_user": "#fb923c",
            "resolved": "#a78bfa",
            "closed": "#6b7280",
        }
        color = colors.get(obj.status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {"low": "#9ca3af", "medium": "#fb923c", "high": "#f87171", "urgent": "#dc2626"}
        color = colors.get(obj.priority, "#9ca3af")
        return format_html('<span style="color:{};font-weight:700;">{}</span>', color, obj.get_priority_display())
    priority_badge.short_description = "Priority"

    def reply_count_display(self, obj):
        count = obj.replies.count()
        public = obj.replies.filter(is_internal_note=False).count()
        internal = count - public
        return format_html(
            '<span style="color:#4ade80;">{} public</span> / '
            '<span style="color:#9ca3af;">{} internal</span>',
            public, internal,
        )
    reply_count_display.short_description = "Reply Count"

    # ── Actions ───────────────────────────────────────────────

    def resolve_tickets(self, request, queryset):
        now = timezone.now()
        count = 0
        for ticket in queryset.exclude(status__in=["resolved", "closed"]):
            ticket.status = "resolved"
            ticket.resolved_at = now
            ticket.save(update_fields=["status", "resolved_at"])
            Notification.send(
                user=ticket.user,
                notification_type="ticket_resolved",
                title=f"Ticket #{ticket.ticket_number} Resolved ✅",
                message="Your support ticket has been resolved. Reopen if needed.",
                action_url=f"/support/tickets/{ticket.pk}/",
            )
            count += 1
        self.message_user(request, f"✅ {count} ticket(s) resolved.")
    resolve_tickets.short_description = "✅ Mark as Resolved"

    def close_tickets(self, request, queryset):
        count = queryset.exclude(status="closed").update(status="closed")
        self.message_user(request, f"🔒 {count} ticket(s) closed.")
    close_tickets.short_description = "🔒 Close selected tickets"

    def reopen_tickets(self, request, queryset):
        count = queryset.filter(status__in=["resolved", "closed"]).update(status="open")
        for ticket in queryset.filter(status="open"):
            Notification.send(
                user=ticket.user,
                notification_type="ticket_reopened",
                title=f"Ticket #{ticket.ticket_number} Reopened",
                message="Your ticket has been reopened and will be reviewed.",
                action_url=f"/support/tickets/{ticket.pk}/",
            )
        self.message_user(request, f"🔄 {count} ticket(s) reopened.")
    reopen_tickets.short_description = "🔄 Reopen tickets"

    def assign_to_me(self, request, queryset):
        queryset.update(assigned_to=request.user)
        self.message_user(request, f"👤 {queryset.count()} ticket(s) assigned to you.")
    assign_to_me.short_description = "Assign to me"

    def mark_in_progress(self, request, queryset):
        count = queryset.filter(status="open").update(status="in_progress")
        self.message_user(request, f"🔄 {count} ticket(s) moved to In Progress.")
    mark_in_progress.short_description = "Mark In Progress"


@admin.register(TicketReply)
class TicketReplyAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "is_internal_note", "created_at"]
    list_filter = ["is_internal_note"]
    readonly_fields = ["created_at"]
    search_fields = ["ticket__ticket_number", "author__email"]

"""Recordings admin — enhanced with file management"""
import os
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from apps.recordings.models import RecordingSession, WebRTCSignal, RecordingChunk


class RecordingChunkInline(admin.TabularInline):
    model = RecordingChunk
    extra = 0
    readonly_fields = ["created_at", "file_size_display"]

    def file_size_display(self, obj):
        if not obj.file:
            return "—"
        try:
            size = os.path.getsize(obj.file.path)
            return f"{size / (1024*1024):.2f} MB"
        except Exception:
            return "N/A"
    file_size_display.short_description = "Size"


@admin.register(RecordingSession)
class RecordingSessionAdmin(admin.ModelAdmin):
    list_display = [
        "short_id", "user_a", "user_b", "status", "duration_display",
        "quality_score", "upload_status_badge", "earnings_amount",
        "files_available", "total_file_size", "requested_at",
    ]
    list_filter = ["status", "upload_status", "sample_rate", "earnings_calculated"]
    search_fields = ["user_a__email", "user_b__email", "session_id"]
    readonly_fields = [
        "session_id", "requested_at", "accepted_at", "started_at", "ended_at",
        "duration_display", "drive_link", "drive_file_id",
        "file_download_links", "file_sizes_display",
    ]
    ordering = ["-requested_at"]
    inlines = [RecordingChunkInline]
    fieldsets = (
        ("Session", {
            "fields": ("session_id", "user_a", "user_b", "status", "sample_rate", "room_name"),
        }),
        ("Timing", {
            "fields": ("requested_at", "accepted_at", "started_at", "ended_at", "duration_display"),
        }),
        ("Files", {
            "fields": ("channel_a_file", "channel_b_file", "mixed_file", "file_format",
                       "file_sizes_display", "file_download_links"),
        }),
        ("Google Drive", {
            "fields": ("drive_file_id", "drive_link", "upload_status", "upload_attempts", "last_upload_attempt"),
        }),
        ("Quality", {
            "fields": ("quality_score", "signal_to_noise", "quality_flags"),
        }),
        ("Earnings", {
            "fields": ("earnings_calculated", "earnings_amount", "per_minute_rate_used"),
        }),
        ("Metadata", {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
    )

    def short_id(self, obj):
        return str(obj.session_id)[:12]
    short_id.short_description = "Session ID"

    def upload_status_badge(self, obj):
        colors = {
            "pending": "#9ca3af", "uploading": "#60a5fa", "uploaded": "#4ade80",
            "failed": "#f87171", "retrying": "#fb923c",
        }
        color = colors.get(obj.upload_status, "#9ca3af")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_upload_status_display(),
        )
    upload_status_badge.short_description = "Upload"

    def files_available(self, obj):
        parts = []
        if obj.channel_a_file and obj.channel_a_file.name:
            parts.append('<span style="color:#4ade80;">A</span>')
        if obj.channel_b_file and obj.channel_b_file.name:
            parts.append('<span style="color:#60a5fa;">B</span>')
        if obj.mixed_file and obj.mixed_file.name:
            parts.append('<span style="color:#a78bfa;">M</span>')
        if not parts:
            return format_html('<span style="color:#6b7280;">—</span>')
        return mark_safe(" · ".join(parts))
    files_available.short_description = "Files"
    files_available.allow_tags = True

    def total_file_size(self, obj):
        total = 0
        for field in [obj.channel_a_file, obj.channel_b_file, obj.mixed_file]:
            if field and field.name:
                try:
                    total += os.path.getsize(field.path)
                except Exception:
                    pass
        if total == 0:
            return "—"
        if total > 1024 * 1024:
            return f"{total / (1024*1024):.1f} MB"
        return f"{total / 1024:.1f} KB"
    total_file_size.short_description = "Total Size"

    def file_sizes_display(self, obj):
        rows = []
        for label, field in [("Channel A", obj.channel_a_file), ("Channel B", obj.channel_b_file), ("Mixed", obj.mixed_file)]:
            if field and field.name:
                try:
                    size = os.path.getsize(field.path)
                    size_str = f"{size / (1024*1024):.2f} MB"
                    exists = "✅" if os.path.exists(field.path) else "❌ missing"
                except Exception:
                    size_str = "N/A"
                    exists = "❓"
                rows.append(f"<b>{label}:</b> {size_str} {exists} — <code>{field.name}</code>")
            else:
                rows.append(f"<b>{label}:</b> <em style='color:#6b7280;'>No file</em>")
        return mark_safe("<br>".join(rows))
    file_sizes_display.short_description = "File Details"

    def file_download_links(self, obj):
        links = []
        base = f"/api/recordings/{obj.session_id}"
        for label, channel, field in [
            ("Channel A", "a", obj.channel_a_file),
            ("Channel B", "b", obj.channel_b_file),
            ("Mixed/Stereo", "mixed", obj.mixed_file),
        ]:
            if field and field.name:
                links.append(
                    f'<a href="{base}/download/?channel={channel}" '
                    f'style="display:inline-block;margin:2px 4px;padding:3px 10px;background:#166534;color:#4ade80;'
                    f'border-radius:6px;font-size:12px;text-decoration:none;" target="_blank">'
                    f'⬇ {label}</a>'
                )
        if not links:
            return mark_safe('<em style="color:#6b7280;">No files available for download</em>')
        return mark_safe("".join(links))
    file_download_links.short_description = "Download Files"

    actions = ["reprocess_drive_uploads", "recalculate_earnings", "delete_recording_files_action", "delete_session_records_action"]

    def reprocess_drive_uploads(self, request, queryset):
        from apps.recordings.tasks import upload_session_to_drive
        for session in queryset:
            upload_session_to_drive.delay(str(session.session_id))
        self.message_user(request, f"Queued {queryset.count()} sessions for Drive upload.")
    reprocess_drive_uploads.short_description = "Re-upload to Google Drive"

    def recalculate_earnings(self, request, queryset):
        from apps.recordings.tasks import process_recording_earnings
        for session in queryset:
            session.earnings_calculated = False
            session.save(update_fields=["earnings_calculated"])
            process_recording_earnings.delay(str(session.session_id))
        self.message_user(request, f"Recalculating earnings for {queryset.count()} sessions.")
    recalculate_earnings.short_description = "Recalculate earnings"

    def delete_recording_files_action(self, request, queryset):
        """Delete physical files from disk, keep session records."""
        from apps.recordings.tasks import cleanup_recording_files
        count = 0
        for session in queryset:
            cleanup_recording_files.delay(str(session.session_id), delete_record=False)
            count += 1
        self.message_user(request, f"Queued file deletion for {count} sessions (records preserved).")
    delete_recording_files_action.short_description = "🗑 Delete audio files (keep records)"

    def delete_session_records_action(self, request, queryset):
        """Delete physical files AND session records from DB."""
        from apps.recordings.tasks import cleanup_recording_files
        count = 0
        for session in queryset:
            cleanup_recording_files.delay(str(session.session_id), delete_record=True)
            count += 1
        self.message_user(request, f"Queued complete deletion for {count} sessions (records + files).")
    delete_session_records_action.short_description = "🗑 Delete audio files + session records"


@admin.register(WebRTCSignal)
class WebRTCSignalAdmin(admin.ModelAdmin):
    list_display = ["session", "sender", "signal_type", "created_at"]
    list_filter = ["signal_type"]
    readonly_fields = ["created_at"]


@admin.register(RecordingChunk)
class RecordingChunkAdmin(admin.ModelAdmin):
    list_display = ["session", "channel", "chunk_index", "duration_seconds", "is_uploaded", "created_at"]
    list_filter = ["channel", "is_uploaded"]
    readonly_fields = ["created_at"]
    search_fields = ["session__session_id"]

"""Marketplace admin — Job Posts, Categories, Applications, Fixed Tasks."""
import csv
import io
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.marketplace.models import (
    AnalyticsSnapshot,
    DynamicSetting,
    FixedTask,
    JobApplication,
    JobMedia,
    JobPosting,
    JobSubmission,
    MarketplaceCategory,
    MarketplaceProfile,
    NotificationTemplate,
)
from apps.notifications.models import Notification


# ──────────────────────────────────────────────────────────────
# Inlines
# ──────────────────────────────────────────────────────────────

class JobMediaInline(admin.TabularInline):
    model = JobMedia
    extra = 1
    fields = ["media_type", "title", "file", "external_url", "caption", "sort_order"]


class JobApplicationInline(admin.TabularInline):
    model = JobApplication
    extra = 0
    readonly_fields = ["applicant", "status", "applied_at", "progress_percent_display"]
    fields = ["applicant", "status", "applied_at", "progress_percent_display"]
    can_delete = False
    show_change_link = True

    def progress_percent_display(self, obj):
        p = obj.progress_percent
        color = "#4ade80" if p == 100 else "#60a5fa" if p > 50 else "#fb923c"
        return format_html(
            '<div style="background:#1f2937;border-radius:4px;height:8px;width:100px;">'
            '<div style="background:{};border-radius:4px;height:8px;width:{}px;"></div></div>'
            '<small style="color:{}">{}&nbsp;%</small>',
            color, p, color, p,
        )
    progress_percent_display.short_description = "Progress"


class JobSubmissionInline(admin.TabularInline):
    model = JobSubmission
    extra = 0
    readonly_fields = ["submitted_by", "submission_type", "verification_status", "payment_status", "payment_amount", "created_at"]
    fields = ["submitted_by", "submission_type", "verification_status", "payment_status", "payment_amount", "created_at"]
    can_delete = False
    show_change_link = True


# ──────────────────────────────────────────────────────────────
# MarketplaceCategory
# ──────────────────────────────────────────────────────────────

@admin.register(MarketplaceCategory)
class MarketplaceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "task_mode", "parent", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["task_mode", "is_active"]
    search_fields = ["name", "code"]
    prepopulated_fields = {"code": ("name",)}
    ordering = ["sort_order", "name"]


# ──────────────────────────────────────────────────────────────
# JobPosting
# ──────────────────────────────────────────────────────────────

@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = [
        "job_id", "title", "category", "recruiter", "status_badge",
        "payment_model", "salary_display", "featured_job", "trending_badge",
        "applications_count", "deadline_status", "published_at", "created_at",
    ]
    list_filter = [
        "status", "payment_model", "featured_job", "is_trending",
        "priority_level", "category", "gender_restriction",
    ]
    search_fields = ["job_id", "title", "recruiter__email", "recruiter__full_name"]
    readonly_fields = ["job_id", "published_at", "created_at", "updated_at", "applications_count"]
    ordering = ["-created_at"]
    inlines = [JobMediaInline, JobApplicationInline]
    list_per_page = 30
    date_hierarchy = "created_at"
    save_on_top = True

    fieldsets = (
        ("🗂 Job Identity", {
            "fields": ("job_id", "recruiter", "category", "subcategory", "title", "subtitle",
                       "status", "priority_level", "featured_job", "is_trending", "trending_priority"),
        }),
        ("📝 Description", {
            "fields": ("short_description", "full_description", "requirements", "eligibility"),
            "classes": ("collapse",),
        }),
        ("👥 Targeting", {
            "fields": ("skills_required", "age_restriction_min", "age_restriction_max",
                       "country_restriction", "gender_restriction", "language_restriction",
                       "experience_requirement", "device_requirement"),
            "classes": ("collapse",),
        }),
        ("💰 Payment & Salary", {
            "fields": ("payment_model", "currency", "fixed_amount", "per_minute_rate",
                       "per_hour_rate", "per_task_rate", "per_submission_rate", "dynamic_formula"),
        }),
        ("📊 Limits", {
            "fields": ("daily_limit", "weekly_limit", "monthly_limit", "global_limit", "user_limit"),
            "classes": ("collapse",),
        }),
        ("📁 Submission", {
            "fields": ("submission_type", "instruction_file", "tutorial_pdf",
                       "tutorial_video_url", "youtube_video_url", "loom_video_url",
                       "google_form_link", "google_sheet_link", "documentation_url",
                       "external_links", "field_schema"),
            "classes": ("collapse",),
        }),
        ("🖼 Media", {
            "fields": ("banner_image", "thumbnail"),
            "classes": ("collapse",),
        }),
        ("⏰ Schedule", {
            "fields": ("application_deadline", "starts_at", "ends_at",
                       "published_at", "estimated_duration_minutes", "response_sla_hours"),
        }),
        ("⚙ Advanced", {
            "fields": ("is_private", "is_archived", "payment_settings",
                       "limit_rules", "submission_rules", "metadata"),
            "classes": ("collapse",),
        }),
        ("📈 Stats", {
            "fields": ("applications_count", "created_at", "updated_at"),
        }),
    )

    # ── Actions ──────────────────────────────────────────────

    actions = [
        "publish_jobs", "draft_jobs", "pause_jobs", "close_jobs",
        "feature_jobs", "unfeature_jobs",
        "mark_trending", "unmark_trending",
        "extend_deadline_90days",
        "export_jobs_csv",
    ]

    def save_model(self, request, obj, form, change):
        """Warn admin if deadline is already in the past."""
        super().save_model(request, obj, form, change)
        if obj.application_deadline and obj.application_deadline < timezone.now():
            self.message_user(
                request,
                f"⚠️ WARNING: The application deadline you set is already in the past ({obj.application_deadline.strftime('%Y-%m-%d %H:%M UTC')}). "
                f"Users will see 'This job is not open for applications.' — "
                f"Please update the deadline to a future date, or use the 'Extend deadline 90 days' action.",
                level="warning",
            )

    def publish_jobs(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status="draft").update(status="published", published_at=now)
        self.message_user(request, f"✅ {updated} job(s) published.")
    publish_jobs.short_description = "Publish selected jobs"

    def draft_jobs(self, request, queryset):
        queryset.update(status="draft")
        self.message_user(request, "↩ Selected jobs moved to Draft.")
    draft_jobs.short_description = "Move to Draft"

    def pause_jobs(self, request, queryset):
        queryset.update(status="paused")
        self.message_user(request, "⏸ Selected jobs paused.")
    pause_jobs.short_description = "Pause selected jobs"

    def close_jobs(self, request, queryset):
        queryset.update(status="closed")
        self.message_user(request, "🔒 Selected jobs closed.")
    close_jobs.short_description = "Close selected jobs"

    def feature_jobs(self, request, queryset):
        queryset.update(featured_job=True)
        self.message_user(request, "⭐ Selected jobs marked as Featured.")
    feature_jobs.short_description = "Mark as Featured"

    def unfeature_jobs(self, request, queryset):
        queryset.update(featured_job=False)
        self.message_user(request, "Selected jobs removed from Featured.")
    unfeature_jobs.short_description = "Remove from Featured"

    def mark_trending(self, request, queryset):
        queryset.update(is_trending=True)
        self.message_user(request, "🔥 Selected jobs marked as Trending.")
    mark_trending.short_description = "Mark as Trending 🔥"

    def unmark_trending(self, request, queryset):
        queryset.update(is_trending=False)
        self.message_user(request, "Selected jobs removed from Trending.")
    unmark_trending.short_description = "Remove from Trending"

    def extend_deadline_90days(self, request, queryset):
        from datetime import timedelta
        count = 0
        for job in queryset:
            job.application_deadline = timezone.now() + timedelta(days=90)
            job.save(update_fields=["application_deadline"])
            count += 1
        self.message_user(request, f"📅 Extended deadline by 90 days for {count} job(s).")
    extend_deadline_90days.short_description = "📅 Extend deadline by 90 days"

    def export_jobs_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="jobs_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["Job ID", "Title", "Category", "Status", "Payment Model",
                         "Amount", "Featured", "Trending", "Applications", "Published At", "Created At"])
        for job in queryset.select_related("category"):
            writer.writerow([
                job.job_id, job.title, job.category.name, job.status,
                job.payment_model, job.fixed_amount, job.featured_job, job.is_trending,
                job.applications.count(), job.published_at, job.created_at,
            ])
        return response
    export_jobs_csv.short_description = "Export to CSV"

    # ── Display helpers ───────────────────────────────────────

    def status_badge(self, obj):
        colors = {
            "draft": "#9ca3af", "published": "#4ade80", "paused": "#fb923c",
            "closed": "#f87171", "archived": "#6b7280",
        }
        color = colors.get(obj.status, "#9ca3af")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def trending_badge(self, obj):
        if obj.is_trending:
            return format_html('<span style="color:#fb923c;font-weight:700;">🔥 Trending</span>')
        return format_html('<span style="color:#4b5563;">—</span>')
    trending_badge.short_description = "Trending"

    def salary_display(self, obj):
        if obj.payment_model == "fixed":
            return format_html("₹{}", obj.fixed_amount)
        elif obj.payment_model == "per_minute":
            return format_html("₹{}/min", obj.per_minute_rate)
        elif obj.payment_model == "per_hour":
            return format_html("₹{}/hr", obj.per_hour_rate)
        elif obj.payment_model == "per_task":
            return format_html("₹{}/task", obj.per_task_rate)
        elif obj.payment_model == "per_submission":
            return format_html("₹{}/submit", obj.per_submission_rate)
        return obj.get_payment_model_display()
    salary_display.short_description = "Salary"

    def deadline_status(self, obj):
        if not obj.application_deadline:
            return format_html('<span style="color:#9ca3af;">No deadline</span>')
        now = timezone.now()
        if obj.application_deadline < now:
            return format_html(
                '<span style="color:#f87171;font-weight:700;">⚠️ EXPIRED {}</span>',
                obj.application_deadline.strftime("%Y-%m-%d"),
            )
        days_left = (obj.application_deadline - now).days
        color = "#4ade80" if days_left > 30 else "#fb923c" if days_left > 7 else "#f87171"
        return format_html(
            '<span style="color:{};">✅ {} days left</span>', color, days_left
        )
    deadline_status.short_description = "Deadline"

    def applications_count(self, obj):
        return obj.applications.count()
    applications_count.short_description = "Applications"


# ──────────────────────────────────────────────────────────────
# JobApplication
# ──────────────────────────────────────────────────────────────

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "job", "applicant", "status_badge", "progress_bar",
        "gross_amount", "applied_at",
    ]
    list_filter = ["status", "job__category"]
    search_fields = ["job__job_id", "job__title", "applicant__email", "applicant__full_name"]
    readonly_fields = [
        "job", "applicant", "applied_at", "reviewed_at", "assigned_at",
        "submitted_at", "verified_at", "payment_approved_at", "completed_at",
        "progress_percent",
    ]
    ordering = ["-created_at"]
    inlines = [JobSubmissionInline]

    fieldsets = (
        ("Application", {
            "fields": ("job", "applicant", "status", "cover_letter", "expected_rate"),
        }),
        ("Review", {
            "fields": ("assigned_reviewer", "review_note", "submission_note", "verification_note"),
        }),
        ("Payment", {
            "fields": ("gross_amount", "platform_fee_amount", "creator_payout_amount"),
        }),
        ("Timeline", {
            "fields": ("applied_at", "reviewed_at", "assigned_at", "submitted_at",
                       "verified_at", "payment_approved_at", "completed_at"),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "approve_applications", "assign_applications",
        "verify_submissions", "reject_applications", "complete_applications",
    ]

    def status_badge(self, obj):
        colors = {
            "applied": "#9ca3af", "under_review": "#60a5fa", "approved": "#34d399",
            "assigned": "#a78bfa", "submitted": "#fb923c", "verification": "#fbbf24",
            "payment_approved": "#4ade80", "completed": "#22c55e",
            "rejected": "#f87171", "cancelled": "#6b7280",
        }
        color = colors.get(obj.status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        p = obj.progress_percent
        color = "#4ade80" if p == 100 else "#60a5fa" if p > 50 else "#fb923c"
        return format_html(
            '<div style="background:#1f2937;border-radius:4px;height:8px;width:80px;display:inline-block;vertical-align:middle;">'
            '<div style="background:{};border-radius:4px;height:8px;width:{}px;"></div></div> {}%',
            color, int(0.8 * p), p,
        )
    progress_bar.short_description = "Progress"

    def approve_applications(self, request, queryset):
        now = timezone.now()
        for app in queryset.filter(status="applied"):
            app.status = "approved"
            app.reviewed_at = now
            app.save(update_fields=["status", "reviewed_at"])
            Notification.send(
                user=app.applicant,
                notification_type="job_approved",
                title="Application Approved ✅",
                message=f"Your application for '{app.job.title}' has been approved.",
                action_url=f"/my-jobs/",
            )
        self.message_user(request, "✅ Selected applications approved.")
    approve_applications.short_description = "Approve applications"

    def assign_applications(self, request, queryset):
        now = timezone.now()
        for app in queryset.filter(status="approved"):
            app.status = "assigned"
            app.assigned_at = now
            app.save(update_fields=["status", "assigned_at"])
            Notification.send(
                user=app.applicant,
                notification_type="job_assigned",
                title="Task Assigned 📋",
                message=f"You have been assigned '{app.job.title}'. Start working now!",
                action_url=f"/my-jobs/",
            )
        self.message_user(request, "📋 Selected applications assigned.")
    assign_applications.short_description = "Assign to applicants"

    def verify_submissions(self, request, queryset):
        now = timezone.now()
        for app in queryset.filter(status="submitted"):
            app.status = "verification"
            app.verified_at = now
            app.save(update_fields=["status", "verified_at"])
        self.message_user(request, "🔍 Selected moved to Verification.")
    verify_submissions.short_description = "Move to Verification"

    def reject_applications(self, request, queryset):
        queryset.update(status="rejected")
        for app in queryset:
            Notification.send(
                user=app.applicant,
                notification_type="job_rejected",
                title="Application Update",
                message=f"Your application for '{app.job.title}' was not selected.",
                action_url=f"/my-jobs/",
            )
        self.message_user(request, "❌ Selected applications rejected.")
    reject_applications.short_description = "Reject applications"

    def complete_applications(self, request, queryset):
        now = timezone.now()
        for app in queryset.filter(status="payment_approved"):
            app.status = "completed"
            app.completed_at = now
            app.save(update_fields=["status", "completed_at"])
            Notification.send(
                user=app.applicant,
                notification_type="job_completed",
                title="Job Completed 🎉",
                message=f"'{app.job.title}' has been marked as complete. Payment released.",
                action_url=f"/wallet/",
            )
        self.message_user(request, "🎉 Selected applications completed.")
    complete_applications.short_description = "Mark as Completed"


# ──────────────────────────────────────────────────────────────
# JobSubmission
# ──────────────────────────────────────────────────────────────

@admin.register(JobSubmission)
class JobSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "id", "application", "submitted_by", "submission_type",
        "verification_badge", "payment_badge", "payment_amount", "created_at",
    ]
    list_filter = ["verification_status", "payment_status", "submission_type"]
    search_fields = [
        "application__job__job_id", "submitted_by__email", "submitted_by__full_name"
    ]
    readonly_fields = ["submitted_by", "application", "created_at", "verified_at"]
    ordering = ["-created_at"]
    list_per_page = 50

    fieldsets = (
        ("Submission", {
            "fields": ("application", "submitted_by", "submission_type",
                       "text_content", "file_upload", "audio_upload",
                       "video_upload", "image_upload", "external_url"),
        }),
        ("Verification", {
            "fields": ("verification_status", "payment_status", "payment_amount",
                       "verified_by", "verified_at"),
        }),
        ("Metadata", {
            "fields": ("form_payload", "metadata", "created_at"),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "bulk_approve_submissions", "bulk_reject_submissions",
        "bulk_approve_payment", "export_submissions_csv",
    ]

    def verification_badge(self, obj):
        colors = {
            "pending": "#9ca3af", "needs_revision": "#fb923c",
            "approved": "#4ade80", "rejected": "#f87171",
        }
        color = colors.get(obj.verification_status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_verification_status_display())
    verification_badge.short_description = "Verification"

    def payment_badge(self, obj):
        colors = {"pending": "#9ca3af", "processing": "#60a5fa", "paid": "#4ade80", "failed": "#f87171"}
        color = colors.get(obj.payment_status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_payment_status_display())
    payment_badge.short_description = "Payment"

    def bulk_approve_submissions(self, request, queryset):
        now = timezone.now()
        count = 0
        for sub in queryset.filter(verification_status="pending"):
            sub.verification_status = "approved"
            sub.verified_by = request.user
            sub.verified_at = now
            sub.save(update_fields=["verification_status", "verified_by", "verified_at"])
            # Move pending → main balance
            try:
                wallet = sub.submitted_by.wallet
                if sub.payment_amount > 0:
                    wallet.release_pending(sub.payment_amount)
                    sub.payment_status = "paid"
                    sub.save(update_fields=["payment_status"])
            except Exception:
                pass
            Notification.send(
                user=sub.submitted_by,
                notification_type="submission_approved",
                title="Submission Approved ✅",
                message=f"Your submission was approved. ₹{sub.payment_amount} added to wallet.",
                action_url="/wallet/",
            )
            count += 1
        self.message_user(request, f"✅ {count} submissions approved and payment released.")
    bulk_approve_submissions.short_description = "✅ Bulk Approve (release payment)"

    def bulk_reject_submissions(self, request, queryset):
        count = 0
        for sub in queryset.filter(verification_status="pending"):
            sub.verification_status = "rejected"
            sub.verified_by = request.user
            sub.save(update_fields=["verification_status", "verified_by"])
            Notification.send(
                user=sub.submitted_by,
                notification_type="submission_rejected",
                title="Submission Rejected",
                message="Your submission was reviewed and rejected. Please check the guidelines.",
                action_url="/my-jobs/",
            )
            count += 1
        self.message_user(request, f"❌ {count} submissions rejected.")
    bulk_reject_submissions.short_description = "❌ Bulk Reject submissions"

    def bulk_approve_payment(self, request, queryset):
        count = 0
        for sub in queryset.filter(verification_status="approved", payment_status="pending"):
            try:
                wallet = sub.submitted_by.wallet
                if sub.payment_amount > 0:
                    wallet.release_pending(sub.payment_amount)
                sub.payment_status = "paid"
                sub.save(update_fields=["payment_status"])
                count += 1
            except Exception:
                pass
        self.message_user(request, f"💰 {count} payments released.")
    bulk_approve_payment.short_description = "💰 Release pending payments"

    def export_submissions_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="submissions_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["ID", "Job", "User", "Type", "Verification", "Payment", "Amount", "Submitted At"])
        for sub in queryset.select_related("application__job", "submitted_by"):
            writer.writerow([
                sub.id, sub.application.job.job_id, sub.submitted_by.email,
                sub.submission_type, sub.verification_status, sub.payment_status,
                sub.payment_amount, sub.created_at,
            ])
        return response
    export_submissions_csv.short_description = "Export to CSV"


# ──────────────────────────────────────────────────────────────
# FixedTask
# ──────────────────────────────────────────────────────────────

@admin.register(FixedTask)
class FixedTaskAdmin(admin.ModelAdmin):
    list_display = [
        "title", "assigned_to", "priority_badge", "status_badge",
        "amount", "due_date", "created_by", "created_at",
    ]
    list_filter = ["status", "priority", "due_date"]
    search_fields = ["title", "assigned_to__email", "assigned_to__full_name"]
    readonly_fields = ["created_by", "created_at", "submitted_at", "approved_at"]
    ordering = ["-created_at"]
    list_per_page = 40
    date_hierarchy = "created_at"

    fieldsets = (
        ("Task", {
            "fields": ("title", "description", "assigned_to", "created_by",
                       "priority", "status", "due_date", "amount"),
        }),
        ("Instructions", {
            "fields": ("instructions_file",),
        }),
        ("Notes", {
            "fields": ("submission_note", "admin_note"),
        }),
        ("Timeline", {
            "fields": ("created_at", "submitted_at", "approved_at"),
        }),
        ("Meta", {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "assign_tasks", "approve_tasks", "reject_tasks",
        "bulk_approve_and_pay", "export_tasks_csv",
    ]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def priority_badge(self, obj):
        colors = {"low": "#9ca3af", "normal": "#60a5fa", "high": "#fb923c", "urgent": "#f87171"}
        color = colors.get(obj.priority, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_priority_display())
    priority_badge.short_description = "Priority"

    def status_badge(self, obj):
        colors = {
            "pending": "#9ca3af", "assigned": "#60a5fa", "submitted": "#fb923c",
            "approved": "#4ade80", "rejected": "#f87171",
        }
        color = colors.get(obj.status, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def assign_tasks(self, request, queryset):
        count = queryset.filter(status="pending", assigned_to__isnull=False).update(status="assigned")
        for task in queryset.filter(status="assigned"):
            if task.assigned_to:
                Notification.send(
                    user=task.assigned_to,
                    notification_type="task_assigned",
                    title="New Task Assigned 📋",
                    message=f"You have been assigned: {task.title}",
                    action_url="/my-jobs/",
                )
        self.message_user(request, f"📋 {count} tasks assigned.")
    assign_tasks.short_description = "Mark as Assigned"

    def approve_tasks(self, request, queryset):
        now = timezone.now()
        count = 0
        for task in queryset.filter(status="submitted"):
            task.status = "approved"
            task.approved_at = now
            task.save(update_fields=["status", "approved_at"])
            if task.assigned_to:
                Notification.send(
                    user=task.assigned_to,
                    notification_type="task_approved",
                    title="Task Approved ✅",
                    message=f"Your task '{task.title}' was approved.",
                    action_url="/wallet/",
                )
            count += 1
        self.message_user(request, f"✅ {count} tasks approved.")
    approve_tasks.short_description = "Approve tasks"

    def reject_tasks(self, request, queryset):
        count = queryset.filter(status="submitted").update(status="rejected")
        for task in queryset.filter(status="rejected"):
            if task.assigned_to:
                Notification.send(
                    user=task.assigned_to,
                    notification_type="task_rejected",
                    title="Task Rejected",
                    message=f"Task '{task.title}' was rejected. Check admin notes.",
                    action_url="/my-jobs/",
                )
        self.message_user(request, f"❌ {count} tasks rejected.")
    reject_tasks.short_description = "Reject tasks"

    def bulk_approve_and_pay(self, request, queryset):
        now = timezone.now()
        count = 0
        for task in queryset.filter(status="submitted"):
            task.status = "approved"
            task.approved_at = now
            task.save(update_fields=["status", "approved_at"])
            if task.assigned_to and task.amount > 0:
                try:
                    task.assigned_to.wallet.credit(
                        amount=task.amount,
                        description=f"Fixed task payment: {task.title}",
                        transaction_type="task_income",
                    )
                    Notification.send(
                        user=task.assigned_to,
                        notification_type="task_paid",
                        title="Payment Released 💸",
                        message=f"₹{task.amount} added for task: {task.title}",
                        action_url="/wallet/",
                    )
                except Exception:
                    pass
            count += 1
        self.message_user(request, f"💸 {count} tasks approved and paid.")
    bulk_approve_and_pay.short_description = "✅ Approve and Release Payment"

    def export_tasks_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="fixed_tasks_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["Title", "Assigned To", "Priority", "Status", "Amount", "Due Date", "Created By", "Created At"])
        for task in queryset.select_related("assigned_to", "created_by"):
            writer.writerow([
                task.title,
                task.assigned_to.email if task.assigned_to else "",
                task.priority, task.status, task.amount,
                task.due_date,
                task.created_by.email if task.created_by else "",
                task.created_at,
            ])
        return response
    export_tasks_csv.short_description = "Export to CSV"


# ──────────────────────────────────────────────────────────────
# MarketplaceProfile
# ──────────────────────────────────────────────────────────────

@admin.register(MarketplaceProfile)
class MarketplaceProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "xp_points", "tier_label", "onboarding_completed"]
    list_filter = ["role", "onboarding_completed"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["tier_label", "xp_points"]

    def tier_label(self, obj):
        return obj.tier_label
    tier_label.short_description = "Tier"


# ──────────────────────────────────────────────────────────────
# DynamicSetting
# ──────────────────────────────────────────────────────────────

@admin.register(DynamicSetting)
class DynamicSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "group", "label", "value_type", "is_public", "is_editable"]
    list_filter = ["group", "value_type", "is_public"]
    search_fields = ["key", "label", "group"]
    list_editable = ["is_public", "is_editable"]


# ──────────────────────────────────────────────────────────────
# NotificationTemplate
# ──────────────────────────────────────────────────────────────

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["slug", "channel", "subject", "is_active"]
    list_filter = ["channel", "is_active"]
    search_fields = ["slug", "subject"]
    list_editable = ["is_active"]


# ──────────────────────────────────────────────────────────────
# AnalyticsSnapshot
# ──────────────────────────────────────────────────────────────

@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ["snapshot_date", "scope", "source", "created_at"]
    list_filter = ["scope"]
    ordering = ["-snapshot_date"]
    readonly_fields = ["created_at"]

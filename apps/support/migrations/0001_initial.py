# Generated manually to match the pre-upgrade support tables already present in db.sqlite3.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("ticket_number", models.CharField(editable=False, max_length=20, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("description", models.TextField()),
                ("category", models.CharField(choices=[("account", "Account Issues"), ("payment", "Payment / Withdrawal"), ("recording", "Recording Problems"), ("technical", "Technical Issues"), ("abuse", "Abuse Report"), ("other", "Other")], default="other", max_length=30)),
                ("status", models.CharField(choices=[("open", "Open"), ("in_progress", "In Progress"), ("waiting_user", "Waiting for User"), ("resolved", "Resolved"), ("closed", "Closed")], db_index=True, default="open", max_length=20)),
                ("priority", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")], db_index=True, default="medium", max_length=10)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_to", models.ForeignKey(blank=True, limit_choices_to={"is_staff": True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_tickets", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TicketReply",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField()),
                ("attachment", models.FileField(blank=True, null=True, upload_to="support/replies/")),
                ("is_internal_note", models.BooleanField(default=False, help_text="Visible to staff only")),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="support.supportticket")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]

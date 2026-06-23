# Generated manually to match the pre-upgrade wallet tables already present in db.sqlite3.
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
            name="Wallet",
            fields=[
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="wallet", serialize=False, to=settings.AUTH_USER_MODEL)),
                ("available_balance", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("pending_balance", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_earned", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_withdrawn", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("currency", models.CharField(default="INR", max_length=5)),
                ("is_frozen", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("transaction_type", models.CharField(choices=[("credit", "Credit"), ("debit", "Debit"), ("pending", "Pending"), ("bonus", "Bonus"), ("referral", "Referral Bonus"), ("withdrawal", "Withdrawal"), ("penalty", "Penalty"), ("adjustment", "Admin Adjustment"), ("daily_reward", "Daily Reward"), ("challenge", "Challenge Reward")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("balance_after", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("reference", models.CharField(blank=True, max_length=200)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transactions", to="wallet.wallet")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transactions", to="recordings.recordingsession")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="EarningRate",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("default", "Default"), ("beginner", "Beginner"), ("intermediate", "Intermediate"), ("expert", "Expert"), ("verified_expert", "Verified Expert"), ("premium", "Premium Session")], max_length=30, unique=True)),
                ("per_minute_rate", models.DecimalField(decimal_places=2, max_digits=8)),
                ("per_hour_rate", models.DecimalField(decimal_places=2, max_digits=8)),
                ("bonus_multiplier", models.FloatField(default=1.0)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="Withdrawal",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("method", models.CharField(choices=[("bank_transfer", "Bank Transfer"), ("upi", "UPI"), ("paytm", "Paytm")], max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("under_review", "Under Review"), ("approved", "Approved"), ("rejected", "Rejected"), ("paid", "Paid"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("bank_name", models.CharField(blank=True, max_length=200)),
                ("account_number", models.CharField(blank=True, max_length=50)),
                ("ifsc_code", models.CharField(blank=True, max_length=20)),
                ("account_holder_name", models.CharField(blank=True, max_length=200)),
                ("upi_id", models.CharField(blank=True, max_length=100)),
                ("admin_note", models.TextField(blank=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("transaction_ref", models.CharField(blank=True, max_length=200)),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processed_withdrawals", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="withdrawals", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BonusCampaign",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("condition_type", models.CharField(choices=[("recordings_in_day", "Recordings completed in a day"), ("hours_in_week", "Hours recorded in a week"), ("first_recording", "First recording"), ("referral_count", "Referral count"), ("login_streak", "Login streak")], max_length=50)),
                ("condition_value", models.FloatField()),
                ("reward_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_active", models.BooleanField(default=True)),
                ("max_uses_per_user", models.IntegerField(default=1)),
            ],
        ),
    ]

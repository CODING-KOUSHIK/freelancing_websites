# Adds the enterprise wallet balances and recharge master data.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="wallet",
            name="processing_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="wallet",
            name="bonus_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="wallet",
            name="referral_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="wallet",
            name="lifetime_earnings",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name="RechargeOperator",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("code", models.SlugField(max_length=100, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="RechargePlan",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("circle", models.CharField(blank=True, max_length=100)),
                ("plan_name", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("validity_days", models.PositiveIntegerField(default=0)),
                ("data_allowance", models.CharField(blank=True, max_length=100)),
                ("talktime", models.CharField(blank=True, max_length=100)),
                ("cashback_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("commission_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("external_plan_id", models.CharField(blank=True, max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plans", to="wallet.rechargeoperator")),
            ],
            options={
                "ordering": ["sort_order", "amount", "plan_name"],
            },
        ),
        migrations.CreateModel(
            name="RechargeOrder",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("mobile_number", models.CharField(max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("success", "Success"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="pending", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("cashback_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("commission_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("transaction_ref", models.CharField(blank=True, max_length=200)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="wallet.rechargeoperator")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="wallet.rechargeplan")),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processed_recharge_orders", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recharge_orders", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

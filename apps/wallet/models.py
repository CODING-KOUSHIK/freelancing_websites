"""Wallet app - Wallet, Transactions, EarningRates, Withdrawals, Bonuses, Recharge"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel


def as_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class Wallet(models.Model):
    """One wallet per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
        primary_key=True,
    )
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    processing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    referral_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifetime_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=5, default="INR")
    is_frozen = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"

    def __str__(self):
        return f"Wallet({self.user.full_name}) â‚¹{self.available_balance}"

    def credit(self, amount, description="", transaction_type="credit", reference=""):
        """Atomically credit the wallet."""
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            self.available_balance += amount
            self.total_earned += amount
            self.lifetime_earnings += amount
            if transaction_type in {"bonus", "admin_bonus", "daily_reward", "challenge"}:
                self.bonus_balance += amount
            if transaction_type in {"referral", "referral_bonus"}:
                self.referral_balance += amount
            self.save(
                update_fields=[
                    "available_balance",
                    "total_earned",
                    "lifetime_earnings",
                    "bonus_balance",
                    "referral_balance",
                    "updated_at",
                ]
            )
            Transaction.objects.create(
                wallet=self,
                transaction_type=transaction_type,
                amount=amount,
                balance_after=self.available_balance,
                description=description,
                reference=reference,
            )

    def debit(self, amount, description="", reference=""):
        """Atomically debit the wallet. Raises ValueError if insufficient funds."""
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            if self.available_balance < amount:
                raise ValueError("Insufficient balance")
            self.available_balance -= amount
            self.save(update_fields=["available_balance", "updated_at"])
            Transaction.objects.create(
                wallet=self,
                transaction_type="debit",
                amount=amount,
                balance_after=self.available_balance,
                description=description,
                reference=reference,
            )

    def move_to_pending(self, amount, description=""):
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            self.pending_balance += amount
            self.save(update_fields=["pending_balance", "updated_at"])
            Transaction.objects.create(
                wallet=self,
                transaction_type="pending",
                amount=amount,
                balance_after=self.available_balance,
                description=description,
            )

    def move_to_processing(self, amount, description=""):
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            self.processing_balance += amount
            self.save(update_fields=["processing_balance", "updated_at"])
            Transaction.objects.create(
                wallet=self,
                transaction_type="processing",
                amount=amount,
                balance_after=self.available_balance,
                description=description,
            )

    def release_pending(self, amount):
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            actual = min(amount, self.pending_balance)
            self.pending_balance -= actual
            self.available_balance += actual
            self.total_earned += actual
            self.lifetime_earnings += actual
            self.save(
                update_fields=[
                    "pending_balance",
                    "available_balance",
                    "total_earned",
                    "lifetime_earnings",
                    "updated_at",
                ]
            )
            Transaction.objects.create(
                wallet=self,
                transaction_type="credit",
                amount=actual,
                balance_after=self.available_balance,
                description="Earnings released from pending",
            )

    def release_processing(self, amount):
        from django.db import transaction

        amount = as_decimal(amount)
        with transaction.atomic():
            actual = min(amount, self.processing_balance)
            self.processing_balance -= actual
            self.available_balance += actual
            self.total_earned += actual
            self.lifetime_earnings += actual
            self.save(
                update_fields=[
                    "processing_balance",
                    "available_balance",
                    "total_earned",
                    "lifetime_earnings",
                    "updated_at",
                ]
            )
            Transaction.objects.create(
                wallet=self,
                transaction_type="credit",
                amount=actual,
                balance_after=self.available_balance,
                description="Earnings released from processing",
            )


class Transaction(TimestampedModel):
    """Immutable ledger entry for every wallet movement."""

    TYPE_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("recording_income", "Recording Income"),
        ("task_income", "Task Income"),
        ("bonus", "Bonus"),
        ("referral", "Referral Bonus"),
        ("referral_bonus", "Referral Bonus"),
        ("admin_bonus", "Admin Bonus"),
        ("recharge", "Recharge"),
        ("withdrawal", "Withdrawal"),
        ("penalty", "Penalty"),
        ("adjustment", "Admin Adjustment"),
        ("refund", "Refund"),
        ("daily_reward", "Daily Reward"),
        ("challenge", "Challenge Reward"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=500, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    session = models.ForeignKey(
        "recordings.RecordingSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "-created_at"]),
            models.Index(fields=["transaction_type"]),
        ]

    def __str__(self):
        return f"{self.transaction_type.upper()} â‚¹{self.amount} [{self.wallet.user.email}]"


class EarningRate(TimestampedModel):
    """Admin-configurable per-minute/hour earning rates by category."""

    CATEGORY_CHOICES = [
        ("default", "Default"),
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("expert", "Expert"),
        ("verified_expert", "Verified Expert"),
        ("premium", "Premium Session"),
    ]

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, unique=True)
    per_minute_rate = models.DecimalField(max_digits=8, decimal_places=2)
    per_hour_rate = models.DecimalField(max_digits=8, decimal_places=2)
    bonus_multiplier = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Earning Rate"
        verbose_name_plural = "Earning Rates"

    def __str__(self):
        return f"{self.category}: â‚¹{self.per_minute_rate}/min | â‚¹{self.per_hour_rate}/hr"


class Withdrawal(TimestampedModel):
    """User withdrawal requests with approval workflow."""

    METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("upi", "UPI"),
        ("paytm", "Paytm"),
        ("phonepe", "PhonePe"),
        ("google_pay", "Google Pay"),
        ("razorpay_payout", "Razorpay Payout"),
        ("cashfree_payout", "Cashfree Payout"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)

    bank_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    account_holder_name = models.CharField(max_length=200, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)

    admin_note = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_withdrawals",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    transaction_ref = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Withdrawal"
        verbose_name_plural = "Withdrawals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Withdrawal â‚¹{self.amount} by {self.user.email} [{self.status}]"


class BonusCampaign(TimestampedModel):
    """Admin-created bonus campaigns."""

    CONDITION_TYPES = [
        ("recordings_in_day", "Recordings completed in a day"),
        ("hours_in_week", "Hours recorded in a week"),
        ("first_recording", "First recording"),
        ("referral_count", "Referral count"),
        ("login_streak", "Login streak"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    condition_type = models.CharField(max_length=50, choices=CONDITION_TYPES)
    condition_value = models.FloatField()
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    max_uses_per_user = models.IntegerField(default=1)

    class Meta:
        verbose_name = "Bonus Campaign"
        verbose_name_plural = "Bonus Campaigns"

    def __str__(self):
        return f"{self.name} (â‚¹{self.reward_amount})"


class RechargeOperator(TimestampedModel):
    """Editable recharge operator master data."""

    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class RechargePlan(TimestampedModel):
    """Database-backed recharge plan."""

    operator = models.ForeignKey(RechargeOperator, on_delete=models.CASCADE, related_name="plans")
    circle = models.CharField(max_length=100, blank=True)
    plan_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.PositiveIntegerField(default=0)
    data_allowance = models.CharField(max_length=100, blank=True)
    talktime = models.CharField(max_length=100, blank=True)
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    external_plan_id = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "amount", "plan_name"]
        indexes = [
            models.Index(fields=["operator", "circle", "is_active"]),
        ]

    def __str__(self):
        return f"{self.operator.name} - {self.plan_name}"


class RechargeOrder(TimestampedModel):
    """Recharge request record for future payout and recharge integrations."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recharge_orders")
    operator = models.ForeignKey(RechargeOperator, on_delete=models.PROTECT, related_name="orders")
    plan = models.ForeignKey(RechargePlan, on_delete=models.PROTECT, related_name="orders", null=True, blank=True)
    mobile_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_ref = models.CharField(max_length=200, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_recharge_orders",
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.mobile_number} - {self.amount}"

"""Celery tasks — Wallet: pending earnings, daily rewards, bonus campaigns"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def process_pending_earnings():
    """Release earnings from pending to available after hold period (default 24h)."""
    from apps.wallet.models import Wallet, Transaction
    from django.utils import timezone
    from datetime import timedelta

    hold_cutoff = timezone.now() - timedelta(hours=24)
    # Find pending transactions older than 24h
    pending_txns = Transaction.objects.filter(
        transaction_type="pending",
        created_at__lte=hold_cutoff,
    ).select_related("wallet")

    for txn in pending_txns:
        try:
            txn.wallet.release_pending(txn.amount)
            txn.transaction_type = "released"
            txn.save(update_fields=["transaction_type"])
            logger.info("Released ₹%s for user %s", txn.amount, txn.wallet.user.email)
        except Exception as e:
            logger.exception("Error releasing pending for txn %s: %s", txn.id, e)

    logger.info("process_pending_earnings complete: %d transactions processed", pending_txns.count())


@shared_task
def grant_daily_login_rewards():
    """Grant daily login bonus to users who logged in today."""
    from apps.accounts.models import CustomUser
    from apps.wallet.models import Wallet, BonusCampaign
    from apps.notifications.models import Notification
    from datetime import date

    today = date.today()
    users = CustomUser.objects.filter(
        last_login_date=today,
        is_active=True,
        is_banned=False,
    )

    daily_reward_amount = 5  # Default ₹5 — configurable via SiteSettings
    from apps.core.models import SiteSettings
    reward_str = SiteSettings.get("daily_login_reward", "5")
    try:
        daily_reward_amount = float(reward_str)
    except (ValueError, TypeError):
        pass

    for user in users:
        wallet, _ = Wallet.objects.get_or_create(user=user)
        # Check if already given today
        already_given = wallet.transactions.filter(
            transaction_type="daily_reward",
            created_at__date=today,
        ).exists()
        if not already_given:
            wallet.credit(
                amount=daily_reward_amount,
                description="Daily login reward",
                transaction_type="daily_reward",
            )
            Notification.send(
                user=user,
                notification_type="daily_reward",
                title="Daily Reward! 🎁",
                message=f"You earned ₹{daily_reward_amount} for logging in today!",
                action_url="/wallet/",
            )
    logger.info("Daily rewards granted to %d users", users.count())


@shared_task
def check_bonus_campaigns():
    """Evaluate active bonus campaigns and credit eligible users."""
    from apps.wallet.models import BonusCampaign, Wallet
    from apps.recordings.models import RecordingSession
    from apps.accounts.models import CustomUser
    from apps.notifications.models import Notification
    from datetime import date
    from django.db.models import Count, Sum

    today = date.today()
    campaigns = BonusCampaign.objects.filter(
        is_active=True,
        start_date__lte=today,
        end_date__gte=today,
    )

    for campaign in campaigns:
        users = CustomUser.objects.filter(is_active=True, is_banned=False)
        for user in users:
            wallet, _ = Wallet.objects.get_or_create(user=user)
            already = wallet.transactions.filter(
                transaction_type="bonus",
                description__contains=str(campaign.pk),
            ).count()
            if already >= campaign.max_uses_per_user:
                continue

            # Evaluate condition
            meets = False
            if campaign.condition_type == "first_recording":
                meets = RecordingSession.objects.filter(
                    user_a=user, status="completed"
                ).count() == 1
            elif campaign.condition_type == "recordings_in_day":
                count = RecordingSession.objects.filter(
                    user_a=user, status="completed", ended_at__date=today,
                ).count()
                meets = count >= campaign.condition_value

            if meets:
                wallet.credit(
                    amount=campaign.reward_amount,
                    description=f"Bonus: {campaign.name} [id:{campaign.pk}]",
                    transaction_type="bonus",
                )
                Notification.send(
                    user=user,
                    notification_type="system",
                    title=f"Bonus Unlocked: {campaign.name} 🎉",
                    message=f"You earned ₹{campaign.reward_amount} from our bonus campaign!",
                    action_url="/wallet/",
                )

"""Accounts signals — auto-create Wallet and Presence on user creation"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_wallet_and_presence(sender, instance, created, **kwargs):
    if created:
        from apps.marketplace.models import MarketplaceProfile
        from apps.wallet.models import Wallet
        from apps.presence.models import UserPresence
        Wallet.objects.get_or_create(user=instance)
        UserPresence.objects.get_or_create(user=instance)
        MarketplaceProfile.objects.get_or_create(user=instance)

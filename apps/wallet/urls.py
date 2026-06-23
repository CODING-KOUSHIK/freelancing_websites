"""Wallet frontend URLs"""
from django.urls import path
from apps.wallet import template_views

urlpatterns = [
    path("", template_views.wallet_page, name="wallet"),
    path("withdraw/", template_views.withdraw_page, name="withdraw"),
]

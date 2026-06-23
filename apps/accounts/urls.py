"""Accounts frontend URLs — login, register, profile pages"""
from django.urls import path
from apps.accounts import template_views

urlpatterns = [
    path("", template_views.landing_page, name="landing"),
    path("login/", template_views.login_page, name="login"),
    path("register/", template_views.register_page, name="register"),
    path("verify-email/", template_views.verify_email_page, name="verify-email"),
    path("forgot-password/", template_views.forgot_password_page, name="forgot-password"),
    path("profile/", template_views.profile_page, name="profile"),
]

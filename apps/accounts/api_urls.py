"""Accounts API URL patterns"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from apps.accounts import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="api-register"),
    path("verify-otp/", views.VerifyOTPView.as_view(), name="api-verify-otp"),
    path("resend-otp/", views.ResendOTPView.as_view(), name="api-resend-otp"),
    path("login/", views.CustomLoginView.as_view(), name="api-login"),
    path("session-token/", views.SessionTokenView.as_view(), name="api-session-token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="api-token-refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="api-logout"),
    path("profile/", views.ProfileView.as_view(), name="api-profile"),
    path("password-reset/", views.PasswordResetRequestView.as_view(), name="api-password-reset"),
    path("password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="api-password-reset-confirm"),
    path("login-history/", views.LoginHistoryView.as_view(), name="api-login-history"),
    path("kyc/", views.KYCDocumentView.as_view(), name="api-kyc"),
    path("dashboard/", views.DashboardView.as_view(), name="api-dashboard"),
]

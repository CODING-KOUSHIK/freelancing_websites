"""Custom admin portal routes."""
from django.urls import path
from apps.marketplace import template_views


urlpatterns = [
    path("", template_views.portal_dashboard_page, name="portal-dashboard"),
    path("jobs/", template_views.portal_jobs_page, name="portal-jobs"),
    path("wallet/", template_views.portal_wallet_page, name="portal-wallet"),
    path("support/", template_views.portal_support_page, name="portal-support"),
    path("settings/", template_views.portal_settings_page, name="portal-settings"),
]

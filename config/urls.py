"""
Root URL Configuration
AI Voice Data Marketplace
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Custom portal
    path("admin/", include("apps.marketplace.portal_urls")),

    # Frontend pages
    path("", include("apps.marketplace.public_urls")),
    path("", include("apps.accounts.urls")),
    path("jobs/", include("apps.marketplace.urls")),
    path("dashboard/", include("apps.core.urls")),
    path("recordings/", include("apps.recordings.urls")),
    path("wallet/", include("apps.wallet.urls")),
    path("support/", include("apps.support.urls")),
    path("leaderboard/", include("apps.core.leaderboard_urls")),

    # Session auth helpers
    path("session-login/", __import__("apps.accounts.template_views", fromlist=["session_login"]).session_login, name="session-login"),
    path("session-login-otp/", __import__("apps.accounts.template_views", fromlist=["session_login_after_otp"]).session_login_after_otp, name="session-login-otp"),
    path("logout/", __import__("apps.accounts.template_views", fromlist=["logout_view"]).logout_view, name="logout"),

    # REST API
    path("api/auth/", include("apps.accounts.api_urls")),
    path("api/marketplace/", include("apps.marketplace.api_urls")),
    path("api/presence/", include("apps.presence.urls")),
    path("api/recordings/", include("apps.recordings.api_urls")),
    path("api/wallet/", include("apps.wallet.api_urls")),
    path("api/support/", include("apps.support.api_urls")),
    path("api/ratings/", include("apps.ratings.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/dashboard/", include("apps.core.api_urls")),

    # API Schema / Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Health check
    path("health/", include("health_check.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

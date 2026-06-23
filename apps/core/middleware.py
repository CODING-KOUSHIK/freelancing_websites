"""Core middleware — Audit logging & online status tracking"""
import logging
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

AUDIT_PATHS = ["/api/auth/login/", "/api/auth/register/", "/admin/"]


class AuditLogMiddleware(MiddlewareMixin):
    """Log sensitive API calls to AuditLog."""

    def process_response(self, request, response):
        try:
            if request.path in AUDIT_PATHS and request.method == "POST":
                if hasattr(request, "user") and request.user.is_authenticated:
                    from apps.core.models import AuditLog
                    AuditLog.objects.create(
                        user=request.user,
                        action="api_access",
                        ip_address=self._get_ip(request),
                        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                        description=f"{request.method} {request.path} → {response.status_code}",
                    )
        except Exception:
            pass
        return response

    def _get_ip(self, request):
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        return x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")


class OnlineStatusMiddleware(MiddlewareMixin):
    """Update last_seen for authenticated users on each request."""

    def process_request(self, request):
        try:
            if hasattr(request, "user") and request.user.is_authenticated:
                from apps.presence.models import UserPresence
                UserPresence.objects.filter(user=request.user).update(
                    last_seen=timezone.now()
                )
        except Exception:
            pass

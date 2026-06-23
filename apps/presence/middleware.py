"""Presence middleware — Update last_seen on every authenticated request"""
from django.utils import timezone


class OnlineStatusMiddleware:
    """
    Updates UserPresence.last_seen on every authenticated request.
    Does NOT mark online/offline (that's handled by the WebSocket consumer).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Update presence after response so it doesn't slow the request
        if request.user.is_authenticated:
            try:
                from apps.presence.models import UserPresence
                UserPresence.objects.update_or_create(
                    user=request.user,
                    defaults={"last_seen": timezone.now()},
                )
            except Exception:
                pass  # Never block a request due to presence tracking failure
        return response

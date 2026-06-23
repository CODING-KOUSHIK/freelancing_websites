"""
ASGI config — Django Channels entry point
AI Voice Data Marketplace
"""
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.presence.routing import websocket_urlpatterns as presence_ws
from apps.recordings.routing import websocket_urlpatterns as recordings_ws
from apps.notifications.routing import websocket_urlpatterns as notifications_ws

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    presence_ws + recordings_ws + notifications_ws
                )
            )
        ),
    }
)

"""Recordings WebSocket URL routing"""
from django.urls import re_path
from apps.recordings.consumers import RecordingConsumer

websocket_urlpatterns = [
    # Support both /ws/recording/ and /ws/recordings/ for compatibility
    re_path(r"^ws/recording/(?P<session_id>[0-9a-f-]+)/$", RecordingConsumer.as_asgi()),
    re_path(r"^ws/recordings/(?P<session_id>[0-9a-f-]+)/$", RecordingConsumer.as_asgi()),
]

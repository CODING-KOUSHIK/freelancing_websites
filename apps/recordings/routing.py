from django.urls import re_path
from apps.recordings.consumers import RecordingConsumer

websocket_urlpatterns = [
    re_path(r"^ws/recording/(?P<session_id>[0-9a-f-]+)/$", RecordingConsumer.as_asgi()),
]

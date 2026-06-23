"""Recordings frontend URLs"""
from django.urls import path
from apps.recordings import template_views

urlpatterns = [
    path("", template_views.recordings_list_page, name="recordings"),
    path("<uuid:session_id>/", template_views.recording_session_page, name="recording-session"),
]

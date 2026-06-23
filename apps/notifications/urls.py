"""Notifications API URLs"""
from django.urls import path
from apps.notifications.views import NotificationListView, MarkAllReadView

urlpatterns = [
    path("", NotificationListView.as_view(), name="api-notifications"),
    path("mark-read/", MarkAllReadView.as_view(), name="api-notifications-mark-read"),
]

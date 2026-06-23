"""Core API URLs — admin dashboard stats"""
from django.urls import path
from apps.core import api_views

urlpatterns = [
    path("stats/", api_views.AdminDashboardStatsView.as_view(), name="api-admin-stats"),
]

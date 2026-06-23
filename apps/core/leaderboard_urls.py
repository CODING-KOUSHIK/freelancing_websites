"""Core leaderboard URLs"""
from django.urls import path
from apps.core import template_views

urlpatterns = [
    path("", template_views.leaderboard_page, name="leaderboard"),
]

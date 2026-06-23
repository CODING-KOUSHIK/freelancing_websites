"""Core frontend URLs — dashboard"""
from django.urls import path
from apps.core import template_views

urlpatterns = [
    path("", template_views.dashboard_page, name="dashboard"),
]

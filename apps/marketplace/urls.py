"""Marketplace frontend URLs."""
from django.urls import path
from apps.marketplace import template_views


urlpatterns = [
    path("", template_views.jobs_board_page, name="jobs-board"),
    path("<str:job_id>/", template_views.job_detail_page, name="job-detail"),
]

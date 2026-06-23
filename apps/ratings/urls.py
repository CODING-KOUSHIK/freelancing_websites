"""Ratings API URLs"""
from django.urls import path
from apps.ratings.views import SubmitRatingView

urlpatterns = [
    path("", SubmitRatingView.as_view(), name="api-submit-rating"),
]

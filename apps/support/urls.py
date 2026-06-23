"""Support frontend URLs"""
from django.urls import path
from apps.support import template_views

urlpatterns = [
    path("", template_views.tickets_page, name="support"),
    path("tickets/<uuid:pk>/", template_views.ticket_detail_page, name="ticket-detail"),
]

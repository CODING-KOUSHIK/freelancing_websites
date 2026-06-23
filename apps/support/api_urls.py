"""Support API URLs"""
from django.urls import path
from apps.support import views

urlpatterns = [
    path("tickets/", views.TicketListCreateView.as_view(), name="api-tickets"),
    path("tickets/<uuid:pk>/", views.TicketDetailView.as_view(), name="api-ticket-detail"),
    path("tickets/<uuid:ticket_id>/reply/", views.TicketReplyView.as_view(), name="api-ticket-reply"),
    path("admin/tickets/", views.StaffTicketListView.as_view(), name="api-admin-tickets"),
    path("admin/tickets/<uuid:pk>/", views.StaffTicketDetailView.as_view(), name="api-admin-ticket-detail"),
]

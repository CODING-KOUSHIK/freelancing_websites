"""Support API views"""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from apps.support.models import SupportTicket, TicketReply
from apps.support.serializers import (
    SupportTicketSerializer, CreateTicketSerializer,
    CreateReplySerializer, TicketReplySerializer,
)
from apps.notifications.models import Notification


class TicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateTicketSerializer
        return SupportTicketSerializer

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).prefetch_related("replies")

    def perform_create(self, serializer):
        ticket = serializer.save(user=self.request.user)
        Notification.send(
            user=self.request.user,
            notification_type="system",
            title="Ticket Created",
            message=f"Your ticket #{ticket.ticket_number} has been submitted.",
            action_url=f"/support/tickets/{ticket.pk}/",
        )


class TicketDetailView(generics.RetrieveAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).prefetch_related("replies")


class TicketReplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ticket_id):
        try:
            if request.user.is_staff:
                ticket = SupportTicket.objects.get(pk=ticket_id)
            else:
                ticket = SupportTicket.objects.get(pk=ticket_id, user=request.user)
        except SupportTicket.DoesNotExist:
            return Response({"error": "Ticket not found."}, status=404)

        serializer = CreateReplySerializer(data=request.data)
        if serializer.is_valid():
            reply = serializer.save(
                ticket=ticket,
                author=request.user,
                is_internal_note=bool(serializer.validated_data.get("is_internal_note")) if request.user.is_staff else False,
            )
            now = timezone.now()
            updates = ["last_response_at"]
            ticket.last_response_at = now
            if not ticket.first_response_at:
                ticket.first_response_at = now
                updates.append("first_response_at")
            ticket.save(update_fields=updates)
            # Notify assigned staff if any
            if ticket.assigned_to:
                Notification.send(
                    user=ticket.assigned_to,
                    notification_type="ticket_reply",
                    title=f"New reply on #{ticket.ticket_number}",
                    message=f"{request.user.full_name} replied to a ticket.",
                    action_url=f"/admin/support/supportticket/{ticket.pk}/",
                )
            return Response(TicketReplySerializer(reply).data, status=201)
        return Response(serializer.errors, status=400)


class StaffTicketListView(generics.ListAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        return SupportTicket.objects.select_related("user", "assigned_to").prefetch_related("replies")


class StaffTicketDetailView(generics.RetrieveAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get_queryset(self):
        return SupportTicket.objects.select_related("user", "assigned_to").prefetch_related("replies")

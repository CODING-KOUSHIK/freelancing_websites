"""Support serializers"""
from rest_framework import serializers
from apps.support.models import SupportTicket, TicketReply


class TicketReplySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    is_staff = serializers.BooleanField(source="author.is_staff", read_only=True)

    class Meta:
        model = TicketReply
        fields = [
            "id", "author_name", "is_staff", "message",
            "attachment", "is_internal_note", "created_at",
        ]
        read_only_fields = ["is_internal_note"]


class SupportTicketSerializer(serializers.ModelSerializer):
    replies = TicketReplySerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, default=None)

    class Meta:
        model = SupportTicket
        fields = [
            "id", "ticket_number", "title", "description", "category",
            "status", "priority", "assigned_to_name", "replies",
            "first_response_at", "last_response_at", "sla_due_at",
            "escalation_level", "escalated_at", "created_at", "resolved_at",
            "metadata",
        ]
        read_only_fields = [
            "ticket_number",
            "status",
            "priority",
            "assigned_to_name",
            "first_response_at",
            "last_response_at",
            "sla_due_at",
            "escalation_level",
            "escalated_at",
            "resolved_at",
        ]


class CreateTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["title", "description", "category"]


class CreateReplySerializer(serializers.ModelSerializer):
    is_internal_note = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = TicketReply
        fields = ["message", "attachment", "is_internal_note"]

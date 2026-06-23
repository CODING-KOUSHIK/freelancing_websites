"""Recordings serializers"""
from rest_framework import serializers
from apps.recordings.models import RecordingSession, WebRTCSignal, RecordingChunk
from apps.accounts.serializers import PublicUserSerializer


class RecordingSessionSerializer(serializers.ModelSerializer):
    user_a = PublicUserSerializer(read_only=True)
    user_b = PublicUserSerializer(read_only=True)
    duration_display = serializers.ReadOnlyField()

    class Meta:
        model = RecordingSession
        fields = [
            "session_id", "user_a", "user_b", "status", "sample_rate",
            "requested_at", "accepted_at", "started_at", "ended_at",
            "duration_seconds", "duration_display", "quality_score",
            "drive_link", "upload_status", "earnings_amount",
            "per_minute_rate_used", "earnings_calculated", "room_name",
        ]
        read_only_fields = fields


class RecordingRequestSerializer(serializers.Serializer):
    target_user_id = serializers.UUIDField()
    sample_rate = serializers.ChoiceField(choices=["16kHz", "48kHz"], default="48kHz")

    def validate_target_user_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user not found.")
        request_user = self.context["request"].user
        if user == request_user:
            raise serializers.ValidationError("Cannot send a request to yourself.")
        # Check if target is online
        try:
            if not user.presence.is_online:
                raise serializers.ValidationError("Target user is offline.")
        except Exception:
            pass
        return value


class WebRTCSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebRTCSignal
        fields = ["id", "signal_type", "payload", "created_at"]


class RecordingChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordingChunk
        fields = ["id", "channel", "chunk_index", "file", "duration_seconds", "is_uploaded"]

"""Recordings API views"""
import logging
import os
from django.utils import timezone
from django.http import FileResponse, Http404
from django.conf import settings
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

from apps.recordings.models import RecordingSession, RecordingChunk
from apps.recordings.serializers import (
    RecordingSessionSerializer, RecordingRequestSerializer, RecordingChunkSerializer,
)
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


class SendRecordingRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RecordingRequestSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target = User.objects.get(pk=serializer.validated_data["target_user_id"])

            session = RecordingSession.objects.create(
                user_a=request.user,
                user_b=target,
                status="requested",
                sample_rate=serializer.validated_data.get("sample_rate", "48kHz"),
            )

            # Check auto-accept
            if target.auto_accept_requests:
                session.status = "accepted"
                session.accepted_at = timezone.now()
                session.save(update_fields=["status", "accepted_at"])
                Notification.send(
                    user=request.user,
                    notification_type="recording_accepted",
                    title="Request Auto-Accepted",
                    message=f"{target.full_name} has auto-accepted your recording request.",
                    payload={"session_id": str(session.session_id)},
                    action_url=f"/recordings/{session.session_id}/",
                )
            else:
                Notification.send(
                    user=target,
                    notification_type="recording_request",
                    title="New Recording Request 🎙",
                    message=f"{request.user.full_name} wants to do a recording session with you.",
                    payload={"session_id": str(session.session_id), "from_user": str(request.user.pk)},
                    action_url=f"/recordings/{session.session_id}/",
                )

            return Response(
                RecordingSessionSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AcceptRecordingRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(
                session_id=session_id, user_b=request.user, status="requested"
            )
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found or already processed."}, status=404)

        session.status = "accepted"
        session.accepted_at = timezone.now()
        session.save(update_fields=["status", "accepted_at"])

        Notification.send(
            user=session.user_a,
            notification_type="recording_accepted",
            title="Request Accepted! 🎙",
            message=f"{request.user.full_name} accepted your recording request.",
            payload={"session_id": str(session.session_id)},
            action_url=f"/recordings/{session.session_id}/",
        )

        return Response(RecordingSessionSerializer(session).data)


class RejectRecordingRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(
                session_id=session_id, user_b=request.user, status="requested"
            )
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)

        session.status = "rejected"
        session.save(update_fields=["status"])

        Notification.send(
            user=session.user_a,
            notification_type="recording_rejected",
            title="Request Declined",
            message=f"{request.user.full_name} declined your recording request.",
            payload={"session_id": str(session.session_id)},
        )

        return Response({"message": "Request rejected."})


class StartRecordingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(session_id=session_id)
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)

        if str(session.user_a.pk) != str(request.user.pk) and str(session.user_b.pk) != str(request.user.pk):
            return Response({"error": "Unauthorized."}, status=403)

        if session.status not in {"accepted", "in_progress"}:
            return Response({"error": "Session not ready to start."}, status=409)

        updated_fields = []
        if session.status != "in_progress":
            session.status = "in_progress"
            updated_fields.append("status")
        if not session.started_at:
            session.started_at = timezone.now()
            updated_fields.append("started_at")
        if updated_fields:
            session.save(update_fields=updated_fields)

        return Response(RecordingSessionSerializer(session).data)


class EndRecordingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(
                session_id=session_id, status="in_progress"
            )
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found or not in progress."}, status=404)

        if str(session.user_a.pk) != str(request.user.pk) and str(session.user_b.pk) != str(request.user.pk):
            return Response({"error": "Unauthorized."}, status=403)

        session.status = "completed"
        session.ended_at = timezone.now()
        if session.started_at:
            session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
        session.save(update_fields=["status", "ended_at", "duration_seconds"])

        # Trigger earnings
        from apps.recordings.tasks import process_recording_earnings
        process_recording_earnings.delay(str(session.session_id))

        return Response(RecordingSessionSerializer(session).data)


class RecordingHistoryView(generics.ListAPIView):
    serializer_class = RecordingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user)
        ).order_by("-requested_at")


class RecordingDetailView(generics.RetrieveAPIView):
    serializer_class = RecordingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "session_id"

    def get_queryset(self):
        user = self.request.user
        return RecordingSession.objects.filter(Q(user_a=user) | Q(user_b=user))


class UploadChunkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(session_id=session_id, status="in_progress")
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)

        serializer = RecordingChunkSerializer(data=request.data)
        if serializer.is_valid():
            chunk = serializer.save(session=session)
            return Response(RecordingChunkSerializer(chunk).data, status=201)
        return Response(serializer.errors, status=400)


# ─── New: Download Recording File ─────────────────────────────────────────────

class DownloadRecordingView(APIView):
    """
    Download a recording file for a session.
    Query param: ?channel=a|b|mixed  (defaults to mixed, then a)
    Only the participants or staff can download.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = RecordingSession.objects.get(session_id=session_id)
        except RecordingSession.DoesNotExist:
            raise Http404("Session not found.")

        user = request.user
        is_participant = (
            (session.user_a and str(session.user_a.pk) == str(user.pk)) or
            (session.user_b and str(session.user_b.pk) == str(user.pk))
        )
        if not is_participant and not user.is_staff:
            return Response({"error": "Unauthorized."}, status=403)

        channel = request.query_params.get("channel", "mixed")

        file_field = None
        if channel == "a":
            file_field = session.channel_a_file
        elif channel == "b":
            file_field = session.channel_b_file
        else:
            # Try mixed first, fall back to channel_a
            file_field = session.mixed_file or session.channel_a_file

        if not file_field or not file_field.name:
            return Response({"error": "No recording file available for this channel."}, status=404)

        try:
            file_path = file_field.path
            if not os.path.exists(file_path):
                return Response({"error": "File not found on disk."}, status=404)

            # Build a clean filename
            short_id = str(session.session_id)[:8]
            filename = f"recording_{short_id}_ch{channel}.wav"

            response = FileResponse(
                open(file_path, "rb"),
                content_type="audio/wav",
                as_attachment=True,
                filename=filename,
            )
            return response
        except Exception as e:
            logger.exception("Download error for session %s", session_id)
            return Response({"error": "Could not serve file."}, status=500)


# ─── New: Delete Recording Files ──────────────────────────────────────────────

class DeleteRecordingView(APIView):
    """
    Delete a recording session's files from disk and clear file fields in DB.
    Optionally delete the entire session row if ?delete_record=true.
    Participants can delete their own files; staff can delete any.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, session_id):
        try:
            session = RecordingSession.objects.get(session_id=session_id)
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)

        user = request.user
        is_participant = (
            (session.user_a and str(session.user_a.pk) == str(user.pk)) or
            (session.user_b and str(session.user_b.pk) == str(user.pk))
        )
        if not is_participant and not user.is_staff:
            return Response({"error": "Unauthorized."}, status=403)

        delete_record = request.query_params.get("delete_record", "false").lower() == "true"

        # Delete files from disk
        deleted_files = []
        for field_name in ["channel_a_file", "channel_b_file", "mixed_file"]:
            field = getattr(session, field_name)
            if field and field.name:
                try:
                    if os.path.exists(field.path):
                        os.remove(field.path)
                        deleted_files.append(field_name)
                        logger.info("Deleted file %s for session %s", field.path, session_id)
                except Exception as e:
                    logger.warning("Could not delete file %s: %s", field_name, e)

        # Also delete chunks
        chunks_deleted = 0
        for chunk in session.chunks.all():
            if chunk.file and chunk.file.name:
                try:
                    if os.path.exists(chunk.file.path):
                        os.remove(chunk.file.path)
                        chunks_deleted += 1
                except Exception as e:
                    logger.warning("Could not delete chunk file: %s", e)

        if delete_record:
            # Delete the entire session from DB
            session_id_str = str(session.session_id)
            session.delete()
            return Response({
                "message": "Session and all files deleted from database.",
                "session_id": session_id_str,
                "deleted_files": deleted_files,
                "chunks_deleted": chunks_deleted,
            })
        else:
            # Clear the file fields in DB but keep the session record
            session.channel_a_file = None
            session.channel_b_file = None
            session.mixed_file = None
            session.file_size_bytes = 0
            session.upload_status = "pending"
            session.drive_file_id = ""
            session.drive_link = ""
            session.save(update_fields=[
                "channel_a_file", "channel_b_file", "mixed_file",
                "file_size_bytes", "upload_status", "drive_file_id", "drive_link"
            ])
            session.chunks.all().delete()
            return Response({
                "message": "Recording files deleted. Session record preserved.",
                "session_id": str(session.session_id),
                "deleted_files": deleted_files,
                "chunks_deleted": chunks_deleted,
            })


# ─── New: Recording Library (for the full library page) ───────────────────────

class RecordingLibraryView(APIView):
    """
    Returns all sessions for the current user with full file metadata
    for the library UI.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        sessions = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user)
        ).order_by("-requested_at").select_related("user_a", "user_b")

        results = []
        for s in sessions:
            partner = s.user_b if (s.user_a and str(s.user_a.pk) == str(user.pk)) else s.user_a

            def file_info(field):
                if not field or not field.name:
                    return None
                try:
                    size = os.path.getsize(field.path) if os.path.exists(field.path) else 0
                    return {"name": os.path.basename(field.name), "size_bytes": size, "exists": size > 0}
                except Exception:
                    return None

            results.append({
                "session_id": str(s.session_id),
                "status": s.status,
                "status_display": s.get_status_display(),
                "sample_rate": s.sample_rate,
                "requested_at": s.requested_at.isoformat(),
                "duration_seconds": s.duration_seconds,
                "duration_display": s.duration_display,
                "earnings_amount": str(s.earnings_amount),
                "upload_status": s.upload_status,
                "drive_link": s.drive_link,
                "partner": {
                    "id": str(partner.pk) if partner else None,
                    "full_name": partner.full_name if partner else "Unknown",
                    "level": partner.level if partner else "",
                } if partner else None,
                "files": {
                    "channel_a": file_info(s.channel_a_file),
                    "channel_b": file_info(s.channel_b_file),
                    "mixed": file_info(s.mixed_file),
                },
                "chunk_count": s.chunks.count(),
            })

        return Response({"sessions": results, "total": len(results)})

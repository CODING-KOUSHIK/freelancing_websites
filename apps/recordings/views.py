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
        """
        Send a recording request to another user.
        Both requester AND target must have an approved JobApplication
        for the same audio_upload job.
        """
        serializer = RecordingRequestSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        from apps.marketplace.models import JobApplication
        User = get_user_model()

        target_id = serializer.validated_data["target_user_id"]
        job_id = serializer.validated_data.get("job_id")  # optional — validated below

        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return Response({"error": "Target user not found."}, status=404)

        if str(target.pk) == str(request.user.pk):
            return Response({"error": "You cannot send a request to yourself."}, status=400)

        # Find a shared approved job between requester and target
        # (any job type — employer already approved both applicants)
        requester_approved_jobs = set(
            JobApplication.objects.filter(
                applicant=request.user,
                status="approved",
            ).values_list("job_id", flat=True)
        )

        target_approved_jobs = set(
            JobApplication.objects.filter(
                applicant=target,
                status="approved",
            ).values_list("job_id", flat=True)
        )

        shared_jobs = requester_approved_jobs & target_approved_jobs

        if not shared_jobs:
            return Response(
                {"error": "You and this user don't share an approved job. Both must be approved by the same employer."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Use provided job_id if valid, else pick the first shared job
        if job_id and int(job_id) in shared_jobs:
            selected_job_id = int(job_id)
        else:
            selected_job_id = next(iter(shared_jobs))

        requester_application = JobApplication.objects.get(
            applicant=request.user, job_id=selected_job_id
        )

        # Check no active session already exists between these users for this job
        existing = RecordingSession.objects.filter(
            job_application=requester_application,
            status__in=["requested", "accepted", "in_progress"],
        ).first()
        if existing:
            return Response(
                {
                    "error": "You already have an active session for this job.",
                    "session_id": str(existing.session_id),
                },
                status=status.HTTP_409_CONFLICT,
            )

        session = RecordingSession.objects.create(
            user_a=request.user,
            user_b=target,
            status="requested",
            sample_rate=serializer.validated_data.get("sample_rate", "48kHz"),
            job_application=requester_application,
        )

        if target.auto_accept_requests:
            session.status = "accepted"
            session.accepted_at = timezone.now()
            session.save(update_fields=["status", "accepted_at"])
            Notification.send(
                user=request.user,
                notification_type="recording_accepted",
                title="Request Auto-Accepted",
                message=f"{target.full_name} auto-accepted your recording request.",
                payload={"session_id": str(session.session_id)},
                action_url=f"/recordings/{session.session_id}/",
            )
        else:
            Notification.send(
                user=target,
                notification_type="recording_request",
                title="New Recording Request 🎙",
                message=f"{request.user.full_name} wants to record with you.",
                payload={
                    "session_id": str(session.session_id),
                    "from_user": str(request.user.pk),
                },
                action_url=f"/recordings/{session.session_id}/",
            )

        return Response(
            RecordingSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


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


class CancelSessionView(APIView):
    """
    Either user can cancel a session at any stage (requested/accepted/in_progress).
    - Marks session as 'rejected'
    - Broadcasts session.cancelled to the WS room so both users get kicked out
    - Refreshes presence so both reappear in the online list
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = RecordingSession.objects.get(
                session_id=session_id,
                status__in=["requested", "accepted", "in_progress"],
            )
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found or already ended."}, status=404)

        # Only session participants can cancel
        if str(session.user_a_id) != str(request.user.pk) and str(session.user_b_id) != str(request.user.pk):
            return Response({"error": "Unauthorized."}, status=403)

        session.status = "rejected"
        session.ended_at = timezone.now()
        session.save(update_fields=["status", "ended_at"])

        # Broadcast cancellation via WebSocket to kick both users out of room
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"recording_{session_id}",
                {
                    "type": "session.cancelled",
                    "cancelled_by": str(request.user.pk),
                    "cancelled_by_name": request.user.full_name,
                },
            )
            # Also refresh presence so both users reappear in online list
            from apps.presence.consumers import PRESENCE_GROUP
            async_to_sync(channel_layer.group_send)(
                PRESENCE_GROUP,
                {"type": "presence.refresh"},
            )

        return Response({"message": "Session cancelled."})


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


# ─── Partner Picker ────────────────────────────────────────────────────────────

class AvailablePartnersView(APIView):
    """
    Returns a list of users who are:
    1. Approved for the same job as the current user
    2. Currently online (presence.is_online)
    3. Not the current user themselves
    4. Do NOT already have an active session with the current user

    GET /api/recordings/partners/<job_id>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        from apps.marketplace.models import JobApplication, JobPosting
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Validate job exists and is audio_upload
        try:
            job = JobPosting.objects.get(id=job_id, submission_type="audio_upload")
        except JobPosting.DoesNotExist:
            return Response({"error": "Job not found or not a voice recording job."}, status=404)

        # Check current user is approved for this job
        requester_app = JobApplication.objects.filter(
            applicant=request.user,
            job=job,
            status="approved",
        ).first()
        if not requester_app:
            return Response({"error": "You are not approved for this job."}, status=403)

        # Get all OTHER approved applicants for this job
        approved_user_ids = JobApplication.objects.filter(
            job=job,
            status="approved",
        ).exclude(applicant=request.user).values_list("applicant_id", flat=True)

        # Filter to only online users
        online_users = User.objects.filter(
            pk__in=approved_user_ids,
            presence__is_online=True,
        ).select_related("presence").order_by("full_name")

        # Exclude users who already have an active session with the requester
        active_partner_ids = set(
            RecordingSession.objects.filter(
                status__in=["requested", "accepted", "in_progress"],
            ).filter(
                Q(user_a=request.user) | Q(user_b=request.user)
            ).values_list("user_b_id", flat=True)
        ) | set(
            RecordingSession.objects.filter(
                status__in=["requested", "accepted", "in_progress"],
            ).filter(
                Q(user_a=request.user) | Q(user_b=request.user)
            ).values_list("user_a_id", flat=True)
        )
        active_partner_ids.discard(request.user.pk)

        results = []
        for user in online_users:
            if user.pk in active_partner_ids:
                continue
            results.append({
                "id": str(user.pk),
                "full_name": user.full_name,
                "level": user.level,
                "reputation_score": float(user.reputation_score),
                "profile_photo": user.profile_photo.url if user.profile_photo else None,
                "short_name": user.full_name.split()[0] if user.full_name else "?",
            })

        return Response({
            "job_id": job.id,
            "job_title": job.title,
            "job_code": job.job_id,
            "partners": results,
            "total": len(results),
        })


class RecordingStatsView(APIView):
    """
    Returns recording stats for:
    - My personal stats (completed, rejected, pending)
    - Platform-wide stats (used in the online users panel to show counters)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Count, Q as DQ
        user = request.user

        # ── Personal stats ────────────────────────────────────────
        my_sessions = RecordingSession.objects.filter(
            DQ(user_a=user) | DQ(user_b=user)
        )

        personal = {
            "completed": my_sessions.filter(status="completed").count(),
            "in_progress": my_sessions.filter(status="in_progress").count(),
            "requested": my_sessions.filter(status="requested").count(),
            "rejected": my_sessions.filter(status="rejected").count(),
            "cancelled": my_sessions.filter(status="cancelled").count(),
            "total_duration_seconds": sum(
                s.duration_seconds or 0
                for s in my_sessions.filter(status="completed")
            ),
        }

        # ── Platform-wide stats (last 30 days) ────────────────────
        from django.utils.timezone import now
        from datetime import timedelta
        cutoff = now() - timedelta(days=30)

        platform_qs = RecordingSession.objects.filter(requested_at__gte=cutoff)
        platform = {
            "total_requests": platform_qs.count(),
            "completed": platform_qs.filter(status="completed").count(),
            "rejected": platform_qs.filter(status="rejected").count(),
            "in_progress": platform_qs.filter(status="in_progress").count(),
            "success_rate": 0,
        }
        if platform["total_requests"] > 0:
            platform["success_rate"] = round(
                platform["completed"] / platform["total_requests"] * 100, 1
            )

        return Response({
            "personal": personal,
            "platform": platform,
        })


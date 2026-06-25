"""Recordings template views"""
import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from apps.recordings.models import RecordingSession
from django.conf import settings


def _file_meta(field):
    """Return file metadata dict or None if no file."""
    if not field or not field.name:
        return None
    try:
        path = field.path
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        return {
            "exists": exists and size > 0,
            "size_mb": round(size / (1024 * 1024), 2) if size > 0 else 0,
            "size_bytes": size,
        }
    except Exception:
        return None


@login_required
def recordings_list_page(request):
    """Recordings library — all sessions with file metadata for conditional UI."""
    raw_sessions = RecordingSession.objects.filter(
        Q(user_a=request.user) | Q(user_b=request.user)
    ).order_by("-requested_at").select_related("user_a", "user_b").prefetch_related("chunks")[:100]

    sessions = []
    for s in raw_sessions:
        partner = s.user_b if (s.user_a and str(s.user_a.pk) == str(request.user.pk)) else s.user_a
        file_a = _file_meta(s.channel_a_file)
        file_b = _file_meta(s.channel_b_file)
        file_mixed = _file_meta(s.mixed_file)
        has_any_file = any(
            f and f["exists"] for f in [file_a, file_b, file_mixed]
        )
        sessions.append({
            "obj": s,
            "partner": partner,
            "file_a": file_a,
            "file_b": file_b,
            "file_mixed": file_mixed,
            "has_any_file": has_any_file,
            "chunk_count": s.chunks.count(),
        })

    return render(request, "recordings/history.html", {
        "sessions": sessions,
        "total_sessions": len(sessions),
    })


@login_required
def recording_session_page(request, session_id):
    # Fetch session — user must be a participant
    try:
        session = RecordingSession.objects.select_related("user_a", "user_b").get(
            Q(user_a=request.user) | Q(user_b=request.user),
            session_id=session_id,
        )
    except RecordingSession.DoesNotExist:
        messages.error(request, "Recording session not found or you are not a participant.")
        return redirect("/")

    # If session was cancelled/rejected, redirect gracefully instead of showing broken room
    if session.status in ("rejected", "completed"):
        status_label = "cancelled" if session.status == "rejected" else "completed"
        messages.info(request, f"This recording session has already been {status_label}.")
        return redirect("/")

    is_initiator = str(session.user_a.pk) == str(request.user.pk)
    partner = session.user_b if is_initiator else session.user_a

    # Jitsi room name — deterministic, URL-safe, unique per session
    jitsi_room_name = "vm" + str(session.session_id).replace("-", "")[:14]

    context = {
        "session": session,
        "partner": partner,
        "is_initiator": is_initiator,
        "per_minute_rate": settings.DEFAULT_PER_MINUTE_RATE,
        "jitsi_room_name": jitsi_room_name,
    }
    return render(request, "recordings/session.html", context)

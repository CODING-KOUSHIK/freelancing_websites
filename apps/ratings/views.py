"""Ratings API views and URLs"""
from rest_framework import serializers as drf_serializers
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.urls import path

from apps.ratings.models import Rating
from apps.recordings.models import RecordingSession
from apps.notifications.models import Notification


class RatingSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = [
            "id", "session", "score", "feedback",
            "is_abuse_report", "abuse_reason", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SubmitRatingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        score = request.data.get("score")
        feedback = request.data.get("feedback", "")
        is_abuse = request.data.get("is_abuse_report", False)
        abuse_reason = request.data.get("abuse_reason", "")

        if not session_id or not score:
            return Response({"error": "session_id and score are required."}, status=400)

        try:
            session = RecordingSession.objects.get(session_id=session_id, status="completed")
        except RecordingSession.DoesNotExist:
            return Response({"error": "Session not found or not completed."}, status=404)

        user = request.user
        if str(session.user_a.pk) != str(user.pk) and str(session.user_b.pk) != str(user.pk):
            return Response({"error": "Unauthorized."}, status=403)

        if Rating.objects.filter(session=session, rater=user).exists():
            return Response({"error": "You have already rated this session."}, status=400)

        ratee = session.user_b if str(session.user_a.pk) == str(user.pk) else session.user_a

        rating = Rating.objects.create(
            session=session,
            rater=user,
            ratee=ratee,
            score=int(score),
            feedback=feedback,
            is_abuse_report=bool(is_abuse),
            abuse_reason=abuse_reason,
        )

        Notification.send(
            user=ratee,
            notification_type="rating_received",
            title="New Rating Received ⭐",
            message=f"You received a {score}-star rating for your recent recording.",
            action_url="/dashboard/",
        )

        # Check achievements
        from apps.core.tasks import check_achievements
        check_achievements.delay(str(user.pk))

        return Response(RatingSerializer(rating).data, status=201)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.notifications.models import Notification
        notifs = Notification.objects.filter(user=request.user)[:50]
        data = [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "action_url": n.action_url,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ]
        return Response({"count": notifs.count(), "results": data})

    def patch(self, request):
        ids = request.data.get("ids", [])
        from apps.notifications.models import Notification
        Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        return Response({"message": "Marked as read."})


# ─── URL patterns ─────────────────────────────────────────────
ratings_urlpatterns = [
    path("", SubmitRatingView.as_view(), name="api-submit-rating"),
]

notifications_urlpatterns = [
    path("", NotificationListView.as_view(), name="api-notifications"),
    path("mark-read/", NotificationListView.as_view(), name="api-notifications-mark-read"),
]

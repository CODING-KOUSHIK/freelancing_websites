"""Notifications API views"""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.notifications.models import Notification


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
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
        return Response({
            "unread": Notification.objects.filter(user=request.user, is_read=False).count(),
            "results": data,
        })

    def patch(self, request):
        ids = request.data.get("ids", [])
        Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        return Response({"message": "Marked as read."})


class MarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All notifications marked as read."})

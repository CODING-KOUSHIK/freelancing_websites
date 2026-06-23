"""Notifications context processor"""


def notifications(request):
    if request.user.is_authenticated:
        try:
            from apps.notifications.models import Notification
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            return {"unread_notification_count": count}
        except Exception:
            pass
    return {"unread_notification_count": 0}

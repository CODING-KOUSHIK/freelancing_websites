"""Notifications WebSocket Consumer — per-user private channel"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Per-user private notification channel.
    Group name: notifications_{user_pk}
    Receives push notifications sent via Notification.send()
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"notifications_{self.user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send unread count on connect
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "notification.unread_count",
            "count": count,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("type") == "notification.mark_read":
                notif_id = data.get("id")
                if notif_id:
                    await self.mark_read(notif_id)
                    count = await self.get_unread_count()
                    await self.send(text_data=json.dumps({
                        "type": "notification.unread_count",
                        "count": count,
                    }))
            elif data.get("type") == "notification.mark_all_read":
                await self.mark_all_read()
                await self.send(text_data=json.dumps({
                    "type": "notification.unread_count",
                    "count": 0,
                }))
        except Exception as e:
            logger.exception("NotificationConsumer receive error: %s", e)

    # ─── Group message handler ────────────────────────────────

    async def notification_push(self, event):
        """Called when Notification.send() fires group_send."""
        await self.send(text_data=json.dumps({
            "type": "notification.new",
            "id": event["id"],
            "notification_type": event["notification_type"],
            "title": event["title"],
            "message": event["message"],
            "payload": event.get("payload", {}),
            "action_url": event.get("action_url", ""),
            "created_at": event["created_at"],
        }))

    # ─── DB helpers ───────────────────────────────────────────

    @database_sync_to_async
    def get_unread_count(self):
        from apps.notifications.models import Notification
        return Notification.objects.filter(user=self.user, is_read=False).count()

    @database_sync_to_async
    def mark_read(self, notif_id):
        from apps.notifications.models import Notification
        Notification.objects.filter(id=notif_id, user=self.user).update(is_read=True)

    @database_sync_to_async
    def mark_all_read(self):
        from apps.notifications.models import Notification
        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)

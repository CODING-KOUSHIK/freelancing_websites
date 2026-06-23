"""Presence WebSocket Consumer — real-time online/offline tracking"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

PRESENCE_GROUP = "presence_global"


class PresenceConsumer(AsyncWebsocketConsumer):
    """
    Manages real-time user presence.
    - On connect: marks user online, broadcasts updated online list.
    - On disconnect: marks user offline, broadcasts update.
    - Sends heartbeat acknowledgements.
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_group = f"presence_user_{self.user.pk}"

        # Join global presence group
        await self.channel_layer.group_add(PRESENCE_GROUP, self.channel_name)
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        # Mark online in DB
        await self.set_online(True)

        # Broadcast updated list to all
        await self.broadcast_presence()

        # Send current online list to this user
        online_users = await self.get_online_users()
        await self.send(text_data=json.dumps({
            "type": "presence.init",
            "online_users": online_users,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "user") and self.user.is_authenticated:
            await self.set_online(False)
            await self.broadcast_presence()
            await self.channel_layer.group_discard(PRESENCE_GROUP, self.channel_name)
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")
            if msg_type == "heartbeat":
                await self.update_last_seen()
                await self.send(text_data=json.dumps({"type": "heartbeat.ack"}))
        except Exception as e:
            logger.exception("PresenceConsumer receive error: %s", e)

    async def broadcast_presence(self):
        online_users = await self.get_online_users()
        await self.channel_layer.group_send(
            PRESENCE_GROUP,
            {
                "type": "presence.update",
                "online_users": online_users,
            },
        )

    # ─── Group message handlers ───────────────────────────────

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "presence.update",
            "online_users": event["online_users"],
        }))

    async def presence_init(self, event):
        await self.send(text_data=json.dumps(event))

    # ─── DB helpers ───────────────────────────────────────────

    @database_sync_to_async
    def set_online(self, status: bool):
        from apps.presence.models import UserPresence
        presence, _ = UserPresence.objects.get_or_create(user=self.user)
        if status:
            presence.mark_online(channel_name=self.channel_name)
        else:
            presence.mark_offline()

    @database_sync_to_async
    def update_last_seen(self):
        from apps.presence.models import UserPresence
        UserPresence.objects.filter(user=self.user).update(last_seen=timezone.now())

    @database_sync_to_async
    def get_online_users(self):
        from apps.presence.models import UserPresence
        from django.conf import settings
        limit = getattr(settings, "MAX_ONLINE_USERS_DISPLAY", 10)
        presences = (
            UserPresence.objects
            .filter(is_online=True)
            .select_related("user")
            .order_by("-last_seen")[:limit]
        )
        return [
            {
                "id": str(p.user.pk),
                "name": p.user.full_name,
                "avatar": p.user.profile_photo.url if p.user.profile_photo else None,
                "level": p.user.level,
                "reputation": p.user.reputation_score,
                "last_seen": p.last_seen_display,
            }
            for p in presences
        ]

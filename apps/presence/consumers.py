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

    async def presence_refresh(self, event):
        """Called when a recording session starts/ends — re-broadcast fresh online list."""
        await self.broadcast_presence()

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
        from apps.recordings.models import RecordingSession
        from django.db.models import Q
        from django.conf import settings
        from datetime import timedelta

        limit = getattr(settings, "MAX_ONLINE_USERS_DISPLAY", 20)
        now = timezone.now()

        # Auto-cancel truly stale sessions so users aren't stuck forever:
        # - "requested" sessions older than 5 min (partner never responded)
        # - "accepted/in_progress" sessions older than 3 hours (crashed/abandoned)
        RecordingSession.objects.filter(
            status="requested",
            requested_at__lt=now - timedelta(minutes=5),
        ).update(status="rejected", ended_at=now)

        RecordingSession.objects.filter(
            status__in=["accepted", "in_progress"],
            requested_at__lt=now - timedelta(hours=3),
        ).update(status="rejected", ended_at=now)

        # Only hide users in RECENT active sessions (not stale stuck ones)
        busy_user_ids = set(
            RecordingSession.objects.filter(
                status__in=["requested", "accepted", "in_progress"],
                requested_at__gte=now - timedelta(hours=3),  # ignore ancient sessions
            ).values_list("user_a_id", "user_b_id")
        )
        flat_busy_ids = {uid for pair in busy_user_ids for uid in pair if uid}

        presences = (
            UserPresence.objects
            .filter(is_online=True)
            .exclude(user_id__in=flat_busy_ids)
            .exclude(user=self.user)
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

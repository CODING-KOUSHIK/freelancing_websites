"""Recording WebSocket Consumer — WebRTC signaling & session control"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class RecordingConsumer(AsyncWebsocketConsumer):
    """
    Per-session WebRTC signaling consumer.
    Handles: offer, answer, ICE candidates, recording state, disconnect recovery.
    Room: recording_{session_id}
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group = f"recording_{self.session_id}"

        # Verify user belongs to this session
        session = await self.get_session()
        if not session:
            await self.close(code=4004)
            return

        self.session = session
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()
        logger.info("User %s connected to recording room %s", self.user.pk, self.session_id)

        peer_info = await self.register_connection()
        if peer_info["peer_connected"]:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "peer.joined",
                        "user_id": peer_info["peer_id"],
                        "user_name": peer_info["peer_name"],
                    }
                )
            )

        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "peer.joined",
                "user_id": str(self.user.pk),
                "user_name": self.user.full_name,
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group"):
            await self.unregister_connection()
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "peer.left",
                    "user_id": str(self.user.pk),
                    "user_name": self.user.full_name,
                },
            )
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")

            handlers = {
                "webrtc.offer": self.handle_offer,
                "webrtc.answer": self.handle_answer,
                "webrtc.ice_candidate": self.handle_ice,
                "recording.chunk_saved": self.handle_chunk_saved,
                "recording.end": self.handle_end_recording,
                "chat.message": self.handle_chat,
            }

            handler = handlers.get(msg_type)
            if handler:
                await handler(data)
            else:
                logger.warning("Unknown message type: %s", msg_type)

        except json.JSONDecodeError:
            logger.error("Invalid JSON in recording consumer")
        except Exception as e:
            logger.exception("Recording consumer error: %s", e)

    # ─── Signal handlers ──────────────────────────────────────

    async def handle_offer(self, data):
        await self.save_signal("offer", data.get("payload", {}))
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "webrtc.signal",
                "signal_type": "offer",
                "from_user": str(self.user.pk),
                "payload": data.get("payload", {}),
            },
        )

    async def handle_answer(self, data):
        await self.save_signal("answer", data.get("payload", {}))
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "webrtc.signal",
                "signal_type": "answer",
                "from_user": str(self.user.pk),
                "payload": data.get("payload", {}),
            },
        )

    async def handle_ice(self, data):
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "webrtc.signal",
                "signal_type": "ice_candidate",
                "from_user": str(self.user.pk),
                "payload": data.get("payload", {}),
            },
        )

    async def handle_chunk_saved(self, data):
        await self.update_session_metadata({
            "last_chunk_index": data.get("chunk_index"),
            "last_saved_at": timezone.now().isoformat(),
        })

    async def handle_end_recording(self, data):
        await self.mark_session_completed()
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "recording.ended",
                "ended_by": str(self.user.pk),
                "duration": data.get("duration", 0),
            },
        )
        # Trigger earnings calculation
        from apps.recordings.tasks import process_recording_earnings
        process_recording_earnings.delay(self.session_id)

    async def handle_chat(self, data):
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "chat.message",
                "from_user": str(self.user.pk),
                "from_name": self.user.full_name,
                "message": data.get("message", ""),
            },
        )

    # ─── Group message type handlers ──────────────────────────

    async def webrtc_signal(self, event):
        # Forward to THIS consumer's WebSocket, only if not sender
        if event["from_user"] != str(self.user.pk):
            await self.send(text_data=json.dumps(event))

    async def peer_joined(self, event):
        await self.send(text_data=json.dumps(event))

    async def peer_left(self, event):
        await self.send(text_data=json.dumps(event))

    async def recording_ended(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    # ─── DB helpers ───────────────────────────────────────────

    @database_sync_to_async
    def get_session(self):
        from apps.recordings.models import RecordingSession
        try:
            session = RecordingSession.objects.select_related("user_a", "user_b").get(session_id=self.session_id)
            if str(session.user_a.pk) == str(self.user.pk) or str(session.user_b.pk) == str(self.user.pk):
                return session
            return None
        except RecordingSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_signal(self, signal_type, payload):
        from apps.recordings.models import WebRTCSignal
        WebRTCSignal.objects.create(
            session=self.session,
            sender=self.user,
            signal_type=signal_type,
            payload=payload,
        )

    @database_sync_to_async
    def update_session_metadata(self, extra):
        from apps.recordings.models import RecordingSession
        session = RecordingSession.objects.get(session_id=self.session_id)
        metadata = session.metadata or {}
        metadata.update(extra)
        session.metadata = metadata
        session.save(update_fields=["metadata"])

    @database_sync_to_async
    def mark_session_completed(self):
        from apps.recordings.models import RecordingSession
        RecordingSession.objects.filter(session_id=self.session_id).update(
            status="completed",
            ended_at=timezone.now(),
        )

    @database_sync_to_async
    def register_connection(self):
        from apps.recordings.models import RecordingSession

        session = RecordingSession.objects.select_related("user_a", "user_b").get(session_id=self.session_id)
        metadata = session.metadata or {}
        connected_users = set(metadata.get("connected_users", []))

        if str(session.user_a_id) == str(self.user.pk):
            peer = session.user_b
        elif str(session.user_b_id) == str(self.user.pk):
            peer = session.user_a
        else:
            peer = None
        peer_connected = peer is not None and str(peer.pk) in connected_users

        connected_users.add(str(self.user.pk))
        metadata["connected_users"] = sorted(connected_users)
        metadata["last_connected_at"] = timezone.now().isoformat()
        session.metadata = metadata
        session.save(update_fields=["metadata"])

        return {
            "peer_connected": peer_connected,
            "peer_id": str(peer.pk) if peer else "",
            "peer_name": peer.full_name if peer else "Peer",
        }

    @database_sync_to_async
    def unregister_connection(self):
        from apps.recordings.models import RecordingSession

        try:
            session = RecordingSession.objects.get(session_id=self.session_id)
        except RecordingSession.DoesNotExist:
            return

        metadata = session.metadata or {}
        connected_users = set(metadata.get("connected_users", []))
        user_id = str(self.user.pk)
        if user_id in connected_users:
            connected_users.discard(user_id)
            metadata["connected_users"] = sorted(connected_users)
            metadata["last_disconnected_at"] = timezone.now().isoformat()
            session.metadata = metadata
            session.save(update_fields=["metadata"])

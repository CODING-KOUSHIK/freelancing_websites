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

    Key rules:
    - Recording ONLY starts when BOTH users are connected (recording.ready broadcast)
    - Either user can stop recording (recording.end)
    - When recording ends → recording.ended broadcast → Upload button shows for BOTH
    - No auto-start ever
    Room: recording_{session_id}
    """

    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = str(self.scope["url_route"]["kwargs"]["session_id"])
        self.room_group = f"recording_{self.session_id}"

        try:
            # ✅ Accept FIRST so browser's ws.onopen fires immediately
            await self.channel_layer.group_add(self.room_group, self.channel_name)
            await self.accept()

            # Then verify user belongs to this session
            session = await self.get_session()
            if not session:
                logger.warning("Session %s not found for user %s", self.session_id, self.user.pk)
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "code": "session_not_found",
                    "message": "Session not found or you are not a participant.",
                }))
                await self.close(code=4004)
                return

            self.session = session
            logger.info("User %s connected to room %s (status=%s)", self.user.pk, self.session_id, session.status)

            # Register this user as connected
            connection_info = await self.register_connection()

            # Notify room that this user joined
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "peer.joined",
                    "user_id": str(self.user.pk),
                    "user_name": self.user.full_name,
                    "both_connected": connection_info["both_connected"],
                },
            )

            # If BOTH users are now in the room → unlock recording
            if connection_info["both_connected"]:
                logger.info("Both users connected in room %s — broadcasting recording.ready", self.session_id)
                await self.channel_layer.group_send(
                    self.room_group,
                    {
                        "type": "recording.ready",
                        "message": "Both users connected. You can now start recording.",
                    },
                )

        except Exception as exc:
            logger.error("RecordingConsumer.connect error: %s", exc, exc_info=True)
            try:
                await self.close(code=4500)
            except Exception:
                pass

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
                "recording.start": self.handle_start_recording,
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

    async def handle_start_recording(self, data):
        """Mark session as in_progress when user clicks Record button."""
        both = await self.check_both_connected()
        if not both:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Cannot start — waiting for partner to connect.",
            }))
            return

        await self.mark_session_started()
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "recording.started",
                "started_by": str(self.user.pk),
                "started_at": timezone.now().isoformat(),
            },
        )
        # Refresh presence — both users are now busy, remove from online list
        await self.refresh_global_presence()

    async def handle_chunk_saved(self, data):
        await self.update_session_metadata({
            "last_chunk_index": data.get("chunk_index"),
            "last_saved_at": timezone.now().isoformat(),
        })

    async def handle_end_recording(self, data):
        """
        Either user can stop recording.
        Broadcast recording.ended to BOTH users → Upload button shows.
        """
        session = await self.mark_session_completed(data.get("duration", 0))

        # Broadcast to ALL in room → both see the Upload button
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "recording.ended",
                "ended_by": str(self.user.pk),
                "ended_by_name": self.user.full_name,
                "duration": data.get("duration", 0),
                "session_id": self.session_id,
                "show_upload": True,
            },
        )

        # Refresh presence — both users are free again, show in online list
        await self.refresh_global_presence()

        # Trigger earnings calculation
        from apps.recordings.tasks import process_recording_earnings
        process_recording_earnings.delay(self.session_id)

    async def refresh_global_presence(self):
        """Tell all presence consumers to re-broadcast updated online list."""
        from apps.presence.consumers import PRESENCE_GROUP
        await self.channel_layer.group_send(
            PRESENCE_GROUP,
            {"type": "presence.refresh"},
        )

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

    # ─── Group message type handlers (camelCase → snake_case via Django Channels) ──

    async def webrtc_signal(self, event):
        if event["from_user"] != str(self.user.pk):
            await self.send(text_data=json.dumps(event))

    async def peer_joined(self, event):
        await self.send(text_data=json.dumps(event))

    async def peer_left(self, event):
        await self.send(text_data=json.dumps(event))

    async def recording_ready(self, event):
        """Sent when both users are connected — unlocks Record button."""
        await self.send(text_data=json.dumps(event))

    async def recording_started(self, event):
        await self.send(text_data=json.dumps(event))

    async def recording_ended(self, event):
        """Sent to all when recording stops — shows Upload button."""
        await self.send(text_data=json.dumps(event))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def session_cancelled(self, event):
        """Sent when either user cancels — kicks all users out of the room."""
        await self.send(text_data=json.dumps({
            "type": "session.cancelled",
            "cancelled_by": event.get("cancelled_by"),
            "cancelled_by_name": event.get("cancelled_by_name", ""),
        }))

    # ─── DB helpers ───────────────────────────────────────────

    @database_sync_to_async
    def get_session(self):
        from apps.recordings.models import RecordingSession
        try:
            session = RecordingSession.objects.select_related("user_a", "user_b").get(
                session_id=self.session_id
            )
            if (
                str(session.user_a_id) == str(self.user.pk) or
                str(session.user_b_id) == str(self.user.pk)
            ):
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
    def mark_session_started(self):
        from apps.recordings.models import RecordingSession
        RecordingSession.objects.filter(
            session_id=self.session_id, status__in=["accepted"]
        ).update(status="in_progress", started_at=timezone.now())

    @database_sync_to_async
    def mark_session_completed(self, duration=0):
        from apps.recordings.models import RecordingSession
        session = RecordingSession.objects.get(session_id=self.session_id)
        session.status = "completed"
        session.ended_at = timezone.now()
        if session.started_at:
            session.duration_seconds = int(
                (session.ended_at - session.started_at).total_seconds()
            )
        elif duration:
            session.duration_seconds = int(duration)
        session.save(update_fields=["status", "ended_at", "duration_seconds"])
        return session

    @database_sync_to_async
    def check_both_connected(self):
        from apps.recordings.models import RecordingSession
        session = RecordingSession.objects.get(session_id=self.session_id)
        metadata = session.metadata or {}
        connected = set(metadata.get("connected_users", []))
        return (
            str(session.user_a_id) in connected and
            str(session.user_b_id) in connected
        )

    @database_sync_to_async
    def register_connection(self):
        from apps.recordings.models import RecordingSession
        session = RecordingSession.objects.select_related("user_a", "user_b").get(
            session_id=self.session_id
        )
        metadata = session.metadata or {}
        connected = set(metadata.get("connected_users", []))

        connected.add(str(self.user.pk))
        metadata["connected_users"] = sorted(connected)
        metadata["last_connected_at"] = timezone.now().isoformat()
        session.metadata = metadata
        session.save(update_fields=["metadata"])

        # Check if BOTH are now connected
        both_connected = (
            str(session.user_a_id) in connected and
            str(session.user_b_id) in connected
        )

        peer = session.user_b if str(session.user_a_id) == str(self.user.pk) else session.user_a
        return {
            "both_connected": both_connected,
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
        connected = set(metadata.get("connected_users", []))
        connected.discard(str(self.user.pk))
        metadata["connected_users"] = sorted(connected)
        metadata["last_disconnected_at"] = timezone.now().isoformat()
        session.metadata = metadata
        session.save(update_fields=["metadata"])

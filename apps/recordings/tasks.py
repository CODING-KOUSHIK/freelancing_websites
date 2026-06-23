"""Celery tasks — Recordings: earnings calculation, auto-save, Drive upload, file cleanup"""
import logging
import os
from celery import shared_task
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_recording_earnings(self, session_id: str):
    """Calculate and credit earnings for both users after session ends."""
    try:
        from apps.recordings.models import RecordingSession
        from apps.wallet.models import EarningRate, Wallet
        from apps.notifications.models import Notification

        session = RecordingSession.objects.get(session_id=session_id)
        if session.earnings_calculated:
            logger.info("Earnings already calculated for session %s", session_id)
            return

        if session.status != "completed":
            logger.warning("Session %s not completed, skipping earnings", session_id)
            return

        # Calculate duration
        if session.started_at and session.ended_at:
            duration = (session.ended_at - session.started_at).total_seconds()
        else:
            duration = session.duration_seconds

        duration_minutes = Decimal(str(duration / 60))

        # Get rate for user level (use highest level between two users)
        def get_rate(user):
            try:
                rate = EarningRate.objects.get(category=user.level, is_active=True)
            except EarningRate.DoesNotExist:
                rate = EarningRate.objects.filter(category="default", is_active=True).first()
            if not rate:
                from django.conf import settings
                return Decimal(str(getattr(settings, "DEFAULT_PER_MINUTE_RATE", 2.50)))
            return rate.per_minute_rate

        for user in [session.user_a, session.user_b]:
            if not user:
                continue
            rate = get_rate(user)
            amount = (duration_minutes * rate).quantize(Decimal("0.01"))
            wallet, _ = Wallet.objects.get_or_create(user=user)
            wallet.credit(
                amount=amount,
                description=f"Earnings for recording session {str(session.session_id)[:8]}",
                transaction_type="credit",
                reference=str(session.session_id),
            )
            Notification.send(
                user=user,
                notification_type="earnings_credited",
                title="Earnings Credited 🎉",
                message=f"₹{amount} has been added to your wallet for {int(duration_minutes)} minutes of recording.",
                payload={"amount": str(amount), "session_id": str(session.session_id)},
                action_url="/wallet/",
            )
            logger.info("Credited ₹%s to user %s for session %s", amount, user.pk, session_id)

        session.earnings_calculated = True
        session.earnings_amount = amount
        session.per_minute_rate_used = rate
        session.duration_seconds = int(duration)
        session.save(update_fields=["earnings_calculated", "earnings_amount", "per_minute_rate_used", "duration_seconds"])

        # Trigger Drive upload
        upload_session_to_drive.delay(session_id)

    except RecordingSession.DoesNotExist:
        logger.error("Session %s not found", session_id)
    except Exception as exc:
        logger.exception("Error processing earnings for %s", session_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=5, default_retry_delay=120)
def upload_session_to_drive(self, session_id: str):
    """Upload recording files to Google Drive asynchronously."""
    try:
        from apps.recordings.models import RecordingSession
        from apps.drive.service import DriveService

        session = RecordingSession.objects.get(session_id=session_id)
        if session.upload_status == "uploaded":
            return

        session.upload_status = "uploading"
        session.upload_attempts += 1
        session.last_upload_attempt = timezone.now()
        session.save(update_fields=["upload_status", "upload_attempts", "last_upload_attempt"])

        drive = DriveService()
        result = drive.upload_session(session)

        if result:
            session.drive_file_id = result.get("id", "")
            session.drive_link = result.get("webViewLink", "")
            session.upload_status = "uploaded"
            session.save(update_fields=["drive_file_id", "drive_link", "upload_status"])
            logger.info("Session %s uploaded to Drive: %s", session_id, result.get("id"))
        else:
            raise ValueError("Drive upload returned empty result")

    except Exception as exc:
        logger.exception("Drive upload failed for session %s", session_id)
        try:
            from apps.recordings.models import RecordingSession
            RecordingSession.objects.filter(session_id=session_id).update(upload_status="failed")
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task
def auto_save_chunk(session_id: str, channel: str, chunk_index: int, file_path: str):
    """Persist a recording chunk to avoid data loss."""
    try:
        from apps.recordings.models import RecordingSession, RecordingChunk
        session = RecordingSession.objects.get(session_id=session_id)
        chunk, created = RecordingChunk.objects.get_or_create(
            session=session,
            channel=channel,
            chunk_index=chunk_index,
            defaults={"file": file_path},
        )
        if created:
            logger.info("Chunk %d/%s saved for session %s", chunk_index, channel, session_id)
    except Exception as e:
        logger.exception("Auto-save chunk error: %s", e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def cleanup_recording_files(self, session_id: str, delete_record: bool = False):
    """
    Delete all physical recording files for a session from disk.
    If delete_record=True, also removes the DB row.
    Called from the delete API view or can be scheduled for storage cleanup.
    """
    try:
        from apps.recordings.models import RecordingSession

        session = RecordingSession.objects.get(session_id=session_id)
        deleted = []

        # Delete main files
        for field_name in ["channel_a_file", "channel_b_file", "mixed_file"]:
            field = getattr(session, field_name)
            if field and field.name:
                try:
                    if os.path.exists(field.path):
                        os.remove(field.path)
                        deleted.append(field.path)
                        logger.info("Deleted %s for session %s", field.path, session_id)
                except Exception as e:
                    logger.warning("Could not delete %s: %s", field_name, e)

        # Delete chunk files
        for chunk in session.chunks.all():
            if chunk.file and chunk.file.name:
                try:
                    if os.path.exists(chunk.file.path):
                        os.remove(chunk.file.path)
                        deleted.append(chunk.file.path)
                except Exception as e:
                    logger.warning("Could not delete chunk: %s", e)

        # Try to remove the session folder if empty
        try:
            from django.conf import settings
            session_folder = os.path.join(settings.MEDIA_ROOT, "recordings", str(session.session_id))
            if os.path.isdir(session_folder) and not os.listdir(session_folder):
                os.rmdir(session_folder)
                logger.info("Removed empty folder: %s", session_folder)
        except Exception:
            pass

        if delete_record:
            session.delete()
            logger.info("Deleted session record %s from DB", session_id)
        else:
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

        logger.info("cleanup_recording_files: deleted %d files for session %s", len(deleted), session_id)
        return {"deleted": deleted, "count": len(deleted)}

    except RecordingSession.DoesNotExist:
        logger.error("cleanup_recording_files: session %s not found", session_id)
    except Exception as exc:
        logger.exception("cleanup_recording_files failed for %s", session_id)
        raise self.retry(exc=exc)

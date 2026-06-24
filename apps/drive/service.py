"""Google Drive integration service"""
import os
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class DriveService:
    """
    Handles Google Drive API operations:
    - Authenticate via Service Account
    - Create dated folders
    - Upload recording files
    - Generate shareable links
    - Retry logic handled by Celery task
    """

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account

            sa_file = settings.GOOGLE_SERVICE_ACCOUNT_JSON
            if not sa_file or not os.path.exists(sa_file):
                raise FileNotFoundError(f"Service account file not found: {sa_file}")

            credentials = service_account.Credentials.from_service_account_file(
                sa_file,
                scopes=["https://www.googleapis.com/auth/drive"],
            )
            self._service = build("drive", "v3", credentials=credentials)
            return self._service
        except ImportError:
            logger.error("Google API client not installed. Run: pip install google-api-python-client")
            raise
        except Exception as e:
            logger.exception("Failed to initialize Google Drive service: %s", e)
            raise

    def get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get existing folder by name or create it. Returns folder ID."""
        service = self._get_service()
        parent_id = parent_id or settings.GOOGLE_DRIVE_FOLDER_ID

        query = (
            f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            f" and '{parent_id}' in parents and trashed=false"
        )
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])

        if files:
            return files[0]["id"]

        folder_meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=folder_meta, fields="id").execute()
        logger.info("Created Drive folder: %s (id: %s)", folder_name, folder["id"])
        return folder["id"]

    def upload_file(self, file_path: str, file_name: str, folder_id: str, mime_type: str = "audio/wav") -> dict:
        """Upload a local file to Drive and return file metadata."""
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()
        file_meta = {
            "name": file_name,
            "parents": [folder_id],
        }
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        uploaded = (
            service.files()
            .create(body=file_meta, media_body=media, fields="id, webViewLink, webContentLink, size")
            .execute()
        )

        # Make shareable
        service.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        logger.info("Uploaded file %s to Drive as %s", file_name, uploaded["id"])
        return uploaded

    def upload_session(self, session) -> dict:
        """
        Upload recording files for a session to Google Drive.

        Folder structure:
          root / YYYY-MM-DD / session_XXXXXXXX / requester / recording_JOB-XXX_username.wav
          root / YYYY-MM-DD / session_XXXXXXXX / partner   / recording_JOB-XXX_username.wav

        Both files share the SAME filename so they can be easily paired.
        Returns dict with the last uploaded file's id and link.
        """
        try:
            # ── Level 1: Date folder ─────────────────────────────
            date_str = datetime.now().strftime("%Y-%m-%d")
            date_folder_id = self.get_or_create_folder(date_str)

            # ── Level 2: Session folder ──────────────────────────
            session_folder_name = f"session_{str(session.session_id)[:8]}"
            session_folder_id = self.get_or_create_folder(session_folder_name, date_folder_id)

            # ── Level 3: requester / partner sub-folders ─────────
            requester_folder_id = self.get_or_create_folder("requester", session_folder_id)
            partner_folder_id = self.get_or_create_folder("partner", session_folder_id)

            session.drive_folder_id = session_folder_id
            session.save(update_fields=["drive_folder_id"])

            # ── Build the shared filename ─────────────────────────
            # Format: recording_JOB-XXXXXXXX_username.wav
            job_id_str = "NO-JOB"
            if session.job_application and session.job_application.job:
                job_id_str = session.job_application.job.job_id

            requester_username = "unknown"
            partner_username = "unknown"
            if session.user_a:
                requester_username = session.user_a.email.split("@")[0]
                requester_username = "".join(c for c in requester_username if c.isalnum() or c == "_")
            if session.user_b:
                partner_username = session.user_b.email.split("@")[0]
                partner_username = "".join(c for c in partner_username if c.isalnum() or c == "_")

            # Same base name for both files
            shared_filename = f"recording_{job_id_str}_{requester_username}_{partner_username}.wav"

            # ── Upload files ──────────────────────────────────────
            result = {}

            # user_a (requester) → requester/ folder
            if session.channel_a_file and session.channel_a_file.name:
                local_path = session.channel_a_file.path
                if os.path.exists(local_path):
                    uploaded = self.upload_file(local_path, shared_filename, requester_folder_id)
                    result = uploaded
                    logger.info("Uploaded requester file for session %s", session.session_id)
                else:
                    logger.warning("Requester file not found on disk: %s", local_path)

            # user_b (partner) → partner/ folder
            if session.channel_b_file and session.channel_b_file.name:
                local_path = session.channel_b_file.path
                if os.path.exists(local_path):
                    uploaded = self.upload_file(local_path, shared_filename, partner_folder_id)
                    result = result or uploaded
                    logger.info("Uploaded partner file for session %s", session.session_id)
                else:
                    logger.warning("Partner file not found on disk: %s", local_path)

            if not result:
                logger.warning("No files uploaded for session %s", session.session_id)

            return result

        except Exception as e:
            logger.exception("upload_session error: %s", e)
            return {}



class DriveTaskService:
    """Task-level operations for Drive celery tasks."""

    @staticmethod
    def retry_failed_uploads():
        """Find failed uploads and requeue them."""
        from apps.recordings.models import RecordingSession
        from apps.recordings.tasks import upload_session_to_drive

        failed = RecordingSession.objects.filter(
            upload_status="failed",
            upload_attempts__lt=10,
        ).values_list("session_id", flat=True)

        count = 0
        for session_id in failed:
            upload_session_to_drive.delay(str(session_id))
            count += 1
        logger.info("Retried %d failed Drive uploads", count)
        return count

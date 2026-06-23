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
        Organizes and uploads all files for a RecordingSession.
        Structure: root_folder / YYYY-MM-DD / session_id /
        Returns dict with file id and link.
        """
        try:
            date_folder_name = datetime.now().strftime("%Y-%m-%d")
            date_folder_id = self.get_or_create_folder(date_folder_name)
            session_folder_id = self.get_or_create_folder(
                str(session.session_id)[:12], parent_id=date_folder_id
            )
            session.drive_folder_id = session_folder_id
            session.save(update_fields=["drive_folder_id"])

            result = {}
            files_to_upload = []
            if session.mixed_file and session.mixed_file.name:
                files_to_upload.append(("mixed", session.mixed_file))
            elif session.channel_a_file and session.channel_a_file.name:
                files_to_upload.append(("channel_a", session.channel_a_file))
                if session.channel_b_file and session.channel_b_file.name:
                    files_to_upload.append(("channel_b", session.channel_b_file))

            if not files_to_upload:
                logger.warning("No files to upload for session %s", session.session_id)
                return {}

            for label, file_field in files_to_upload:
                local_path = file_field.path
                if os.path.exists(local_path):
                    file_name = f"{session.session_id}_{label}.wav"
                    uploaded = self.upload_file(local_path, file_name, session_folder_id)
                    result = uploaded  # use last uploaded as main link
                else:
                    logger.warning("File not found on disk: %s", local_path)

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

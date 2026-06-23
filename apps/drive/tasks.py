"""Drive Celery tasks — retry failed uploads"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def retry_failed_uploads():
    """Find and re-queue all failed Drive uploads."""
    from apps.drive.service import DriveTaskService
    count = DriveTaskService.retry_failed_uploads()
    logger.info("retry_failed_uploads: re-queued %d failed uploads", count)
    return count

"""
Celery application entry point
AI Voice Data Marketplace
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("voice_marketplace")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ─── Periodic Tasks (Beat schedule) ──────────────────────────
app.conf.beat_schedule = {
    "cleanup-expired-otps": {
        "task": "apps.core.tasks.cleanup_expired_otps",
        "schedule": crontab(minute="*/30"),
    },
    "update-user-levels": {
        "task": "apps.core.tasks.update_user_levels",
        "schedule": crontab(hour="2", minute="0"),  # 2am daily
    },
    "process-pending-earnings": {
        "task": "apps.wallet.tasks.process_pending_earnings",
        "schedule": crontab(hour="*/6"),  # every 6 hours
    },
    "daily-login-rewards": {
        "task": "apps.wallet.tasks.grant_daily_login_rewards",
        "schedule": crontab(hour="0", minute="5"),  # midnight daily
    },
    "fraud-detection-scan": {
        "task": "apps.core.tasks.fraud_detection_scan",
        "schedule": crontab(hour="*/4"),  # every 4 hours
    },
    "retry-failed-drive-uploads": {
        "task": "apps.drive.tasks.retry_failed_uploads",
        "schedule": crontab(minute="*/15"),  # every 15 minutes
    },
}

app.conf.timezone = "UTC"

"""
Async OTP email sender using Celery + Django's email backend.
- Uses Resend (via anymail) on Railway
- Falls back to SMTP locally
- Non-blocking: email is queued to Celery worker instantly
"""
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp_email(receiver_email: str, otp_code: str, purpose: str = "email_verify"):
    """Send OTP email async via Celery task — returns immediately, never blocks."""
    try:
        from apps.core.tasks import send_otp_email_task
        send_otp_email_task.delay(receiver_email, otp_code, purpose)
        logger.info("OTP email queued for %s (purpose: %s)", receiver_email, purpose)
        return True
    except Exception as e:
        logger.warning("Celery unavailable, sending OTP email synchronously: %s", e)
        return _send_otp_sync(receiver_email, otp_code, purpose)


def send_html_email(receiver_email: str, subject: str, html_body: str):
    """Send HTML email async via Celery task."""
    try:
        from apps.core.tasks import send_html_email_task
        send_html_email_task.delay(receiver_email, subject, html_body)
        return True
    except Exception as e:
        logger.warning("Celery unavailable, sending HTML email synchronously: %s", e)
        return _send_html_sync(receiver_email, subject, html_body)


# ─── Sync fallbacks (used if Celery is down) ──────────────────────────────────

def _send_otp_sync(receiver_email: str, otp_code: str, purpose: str):
    """Synchronous OTP send using Django's configured email backend."""
    if purpose == "password_reset":
        subject = "Your Password Reset OTP — VoiceMarket"
        body = (
            f"Your Password Reset OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"If you did not request a password reset, please ignore this email.\n\n"
            f"VoiceMarket Team"
        )
    else:
        subject = "Your Email Verification OTP — VoiceMarket"
        body = (
            f"Welcome to VoiceMarket!\n\n"
            f"Your Email Verification OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"VoiceMarket Team"
        )
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "VoiceMarket <noreply@voicemarket.app>")
        send_mail(subject, body, from_email, [receiver_email], fail_silently=False)
        logger.info("OTP email sent to %s", receiver_email)
        return True
    except Exception as e:
        logger.exception("Failed to send OTP email to %s: %s", receiver_email, e)
        return False


def _send_html_sync(receiver_email: str, subject: str, html_body: str):
    """Synchronous HTML email using Django's configured email backend."""
    import re
    plain = re.sub(r"<[^>]+>", "", html_body).strip()
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "VoiceMarket <noreply@voicemarket.app>")
        msg = EmailMultiAlternatives(subject, plain, from_email, [receiver_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        return True
    except Exception as e:
        logger.exception("Failed to send HTML email to %s: %s", receiver_email, e)
        return False

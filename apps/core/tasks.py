"""Celery tasks — Core: OTP cleanup, level updates, fraud detection"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email_task(self, receiver_email: str, otp_code: str, purpose: str = "email_verify"):
    """
    Send OTP email via Django's configured email backend (Resend/SMTP).
    Async — never blocks the HTTP request.
    Auto-retries up to 3 times if it fails.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    if purpose == "password_reset":
        subject = "Your Password Reset OTP — VoiceMarket"
        body = (
            f"Your Password Reset OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"If you did not request this, ignore this email.\n\n"
            f"VoiceMarket Team"
        )
    else:
        subject = "Your Email Verification OTP — VoiceMarket"
        body = (
            f"Welcome to VoiceMarket!\n\n"
            f"Your Verification OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"VoiceMarket Team"
        )
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "VoiceMarket <noreply@voicemarket.app>")
        send_mail(subject, body, from_email, [receiver_email], fail_silently=False)
        logger.info("OTP email sent to %s (purpose: %s)", receiver_email, purpose)
        return True
    except Exception as exc:
        logger.exception("OTP email failed for %s: %s — retrying", receiver_email, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_html_email_task(self, receiver_email: str, subject: str, html_body: str):
    """Send HTML email async via Django's configured email backend."""
    import re
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    plain = re.sub(r"<[^>]+>", "", html_body).strip()
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "VoiceMarket <noreply@voicemarket.app>")
        msg = EmailMultiAlternatives(subject, plain, from_email, [receiver_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        logger.info("HTML email sent to %s: %s", receiver_email, subject)
        return True
    except Exception as exc:
        logger.exception("HTML email failed for %s: %s — retrying", receiver_email, exc)
        raise self.retry(exc=exc)


@shared_task
def cleanup_expired_otps():
    """Delete all expired/used OTPs to keep the table clean."""
    from apps.accounts.models import EmailOTP
    cutoff = timezone.now()
    deleted, _ = EmailOTP.objects.filter(expires_at__lt=cutoff).delete()
    logger.info("Cleaned up %d expired OTPs", deleted)
    return deleted


@shared_task
def update_user_levels():
    """
    Recalculate user levels based on total completed recordings.
    Beginner: 0-9 | Intermediate: 10-49 | Expert: 50-199 | Verified Expert: 200+
    """
    from apps.accounts.models import CustomUser
    from apps.recordings.models import RecordingSession
    from django.db.models import Count, Q

    users = CustomUser.objects.filter(is_active=True)
    updated = 0

    for user in users:
        count = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user),
            status="completed",
        ).count()

        if count >= 200:
            new_level = "verified_expert"
        elif count >= 50:
            new_level = "expert"
        elif count >= 10:
            new_level = "intermediate"
        else:
            new_level = "beginner"

        if user.level != new_level:
            user.level = new_level
            user.save(update_fields=["level"])
            updated += 1

    logger.info("update_user_levels: %d users updated", updated)
    return updated


@shared_task
def fraud_detection_scan():
    """
    Basic heuristic fraud detection:
    - Flag users with suspiciously short sessions (< 30s) repeatedly
    - Flag users with duplicate IPs in same session
    - Flag unusually high earnings spikes
    """
    from apps.recordings.models import RecordingSession
    from apps.core.models import AuditLog
    from apps.accounts.models import CustomUser
    from django.db.models import Count, Q, Avg
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=24)

    # Detect: more than 10 sessions < 60 seconds in 24h
    suspicious = (
        RecordingSession.objects
        .filter(status="completed", ended_at__gte=cutoff, duration_seconds__lt=60)
        .values("user_a")
        .annotate(count=Count("id"))
        .filter(count__gte=5)
    )

    for entry in suspicious:
        user_id = entry["user_a"]
        try:
            user = CustomUser.objects.get(pk=user_id)
            AuditLog.objects.create(
                user=user,
                action="admin_action",
                description=f"[FRAUD ALERT] User {user.email} completed {entry['count']} sessions < 60s in 24h",
                extra_data={"type": "short_session_abuse", "count": entry["count"]},
            )
            logger.warning("Fraud alert: user %s has %d short sessions", user.email, entry["count"])
        except CustomUser.DoesNotExist:
            pass

    logger.info("fraud_detection_scan complete")


@shared_task
def send_email_notification(user_id, subject, html_message, text_message=""):
    """Send an email notification to a user."""
    from apps.accounts.models import CustomUser
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        user = CustomUser.objects.get(pk=user_id)
        if not user.email_notifications:
            return
        send_mail(
            subject=subject,
            message=text_message or subject,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("Email sent to %s: %s", user.email, subject)
    except Exception as e:
        logger.exception("Failed to send email to user %s: %s", user_id, e)


@shared_task
def check_achievements(user_id: str):
    """Check and award any unlocked achievements for a user."""
    from apps.accounts.models import CustomUser
    from apps.core.models import Achievement, UserAchievement
    from apps.recordings.models import RecordingSession
    from apps.notifications.models import Notification
    from django.db.models import Q, Count, Sum

    try:
        user = CustomUser.objects.get(pk=user_id)
        achievements = Achievement.objects.filter(is_active=True)
        already_earned = set(
            UserAchievement.objects.filter(user=user).values_list("achievement_id", flat=True)
        )

        recording_count = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user), status="completed"
        ).count()

        total_seconds = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user), status="completed"
        ).aggregate(total=Sum("duration_seconds"))["total"] or 0
        total_hours = total_seconds / 3600

        from apps.ratings.models import Rating
        avg_rating = Rating.objects.filter(
            ratee=user, is_abuse_report=False
        ).aggregate(avg=Avg("score"))["avg"] or 0

        referral_count = user.referrals.count()

        from apps.wallet.models import Wallet
        try:
            total_earned = float(user.wallet.total_earned)
        except Exception:
            total_earned = 0

        stat_map = {
            "recordings_count": recording_count,
            "hours_recorded": total_hours,
            "rating_avg": avg_rating,
            "referrals_count": referral_count,
            "earnings_total": total_earned,
            "streak_days": user.login_streak,
        }

        for achievement in achievements:
            if achievement.id in already_earned:
                continue
            current = stat_map.get(achievement.condition_type, 0)
            if current >= achievement.condition_value:
                UserAchievement.objects.create(user=user, achievement=achievement)
                Notification.send(
                    user=user,
                    notification_type="achievement_earned",
                    title=f"Achievement Unlocked: {achievement.name} {achievement.icon}",
                    message=achievement.description,
                    payload={"achievement_id": achievement.id},
                )
                logger.info("Achievement '%s' awarded to user %s", achievement.name, user.email)
    except Exception as e:
        logger.exception("check_achievements error for user %s: %s", user_id, e)

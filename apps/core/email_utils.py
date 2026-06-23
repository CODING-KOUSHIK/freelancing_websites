"""
Direct OTP email sender using smtplib with proper UTF-8 encoding.
Uses Gmail SMTP with app password — no Celery required.
"""
import smtplib
import random
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SENDER_EMAIL = "koushikbiswas029@gmail.com"
APP_PASSWORD = "gwez ifql bdtf umin"


def send_otp_email(receiver_email: str, otp_code: str, purpose: str = "email_verify"):
    """Send OTP to receiver_email using MIMEText for full UTF-8 support."""
    if purpose == "password_reset":
        subject = "Your Password Reset OTP - VoiceMarket"
        body = (
            f"Your Password Reset OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"If you did not request a password reset, please ignore this email.\n\n"
            f"VoiceMarket Team"
        )
    else:
        subject = "Your Email Verification OTP - VoiceMarket"
        body = (
            f"Welcome to VoiceMarket!\n\n"
            f"Your Email Verification OTP is: {otp_code}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"Do not share this OTP with anyone.\n\n"
            f"VoiceMarket Team"
        )

    try:
        # Build a proper MIME message with UTF-8 encoding
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        logger.info("OTP email sent to %s (purpose: %s)", receiver_email, purpose)
        return True
    except Exception as e:
        logger.exception("Failed to send OTP email to %s: %s", receiver_email, e)
        return False


def send_html_email(receiver_email: str, subject: str, html_body: str):
    """Send an HTML email with plain-text fallback via smtplib."""
    import re
    plain = re.sub(r"<[^>]+>", "", html_body).strip()

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        logger.info("Email sent to %s: %s", receiver_email, subject)
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", receiver_email, e)
        return False

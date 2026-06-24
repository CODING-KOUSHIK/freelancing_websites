"""
Docker settings — PostgreSQL + Redis + Daphne.
Used when running inside Docker containers via docker-compose.
"""
from .base import *  # noqa

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ─── CSRF — trust Railway + localhost ────────────────────────────
import os as _csrf_os
_site_url = _csrf_os.environ.get("SITE_URL", "")
CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
if _site_url and _site_url not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(_site_url)


# ─── Session backend: Redis ──────────────────────────────────────
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ─── Static files ───────────────────────────────────────────────
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ─── Celery: use real Redis broker in Docker ─────────────────────
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# ─── Email ─────────────────────────────────────────────────────
import os as _os
_email_backend = _os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

if "anymail" in _email_backend or "resend" in _email_backend:
    # Use Resend via django-anymail (works on Railway)
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {
        "RESEND_API_KEY": _os.environ.get("RESEND_API_KEY", ""),
    }
else:
    # Standard SMTP fallback (works locally)
    EMAIL_BACKEND = _email_backend

# ─── Logging ─────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "colored": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "daphne": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

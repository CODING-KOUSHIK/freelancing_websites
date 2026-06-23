"""Core context processors"""
from apps.core.models import SiteSettings


def site_settings(request):
    return {
        "SITE_NAME": SiteSettings.get("site_name", "AI Voice Marketplace"),
        "SITE_URL": SiteSettings.get("site_url", "http://localhost:8000"),
    }

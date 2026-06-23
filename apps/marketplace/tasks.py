"""Celery tasks for marketplace maintenance."""
from celery import shared_task
from django.utils import timezone

from apps.marketplace.models import AnalyticsSnapshot, JobPosting
from apps.marketplace.repositories import MarketplaceRepository


@shared_task
def snapshot_portal_metrics():
    repository = MarketplaceRepository()
    payload = repository.portal_metrics()
    AnalyticsSnapshot.objects.update_or_create(
        snapshot_date=timezone.now().date(),
        scope="portal",
        defaults={"payload": payload, "source": "celery"},
    )
    return payload


@shared_task
def close_expired_jobs():
    expired = JobPosting.objects.filter(
        status="published",
        application_deadline__lt=timezone.now(),
    )
    count = expired.update(status="closed")
    return {"closed": count}

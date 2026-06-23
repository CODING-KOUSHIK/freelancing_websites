"""Marketplace HTML views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

from apps.marketplace.models import JobPosting, MarketplaceCategory
from apps.marketplace.repositories import MarketplaceRepository


repository = MarketplaceRepository()


def marketing_page(request, slug):
    pages = {
        "about": {
            "title": "About",
            "headline": "A multi-vertical marketplace built for voice, tasks, and enterprise work.",
            "body": "AI Voice Data Marketplace started with voice recording and now supports a modular job marketplace, custom admin portal, wallet workflows, support operations, and analytics at scale.",
        },
        "contact": {
            "title": "Contact",
            "headline": "Talk to the platform team",
            "body": "Use the support center for product questions, partnerships, and enterprise onboarding.",
        },
        "faq": {
            "title": "FAQ",
            "headline": "Answers for workers, recruiters, and operators",
            "body": "The platform supports voice sessions, task jobs, wallet operations, and recruiter workflows in one codebase.",
        },
        "blog": {
            "title": "Blog",
            "headline": "Product updates and marketplace operations",
            "body": "Publish product announcements, earning tips, marketplace playbooks, and new task category launches.",
        },
        "privacy-policy": {
            "title": "Privacy Policy",
            "headline": "Privacy and data handling",
            "body": "The platform stores only what is needed for identity, payout, job processing, and moderation.",
        },
        "terms": {
            "title": "Terms",
            "headline": "Platform terms",
            "body": "Users, recruiters, and administrators must follow marketplace rules, payout policies, and content guidelines.",
        },
        "careers": {
            "title": "Careers",
            "headline": "Join the operator team",
            "body": "We are building a scalable operations layer for marketplace, support, and trust-and-safety work.",
        },
        "success-stories": {
            "title": "Success Stories",
            "headline": "Worker and recruiter outcomes",
            "body": "Track stories about successful recordings, completed tasks, and enterprise training workflows.",
        },
        "pricing": {
            "title": "Pricing",
            "headline": "Flexible pricing for every task type",
            "body": "Use fixed, per minute, per hour, per task, per submission, or dynamic formula pricing per job.",
        },
        "referral": {
            "title": "Referral Program",
            "headline": "Reward growth without hardcoding payout rules",
            "body": "Referral bonuses are controlled through wallet settings and the dynamic settings engine.",
        },
    }
    page = pages.get(slug, pages["about"])
    return render(request, "marketing/page.html", {"page": page, "slug": slug})


@login_required
def jobs_board_page(request):
    categories = repository.categories()
    jobs = repository.public_jobs()[:48]
    return render(
        request,
        "marketplace/jobs.html",
        {
            "categories": categories,
            "jobs": jobs,
        },
    )


@login_required
def job_detail_page(request, job_id):
    job = get_object_or_404(repository.job_detail_queryset(), job_id=job_id)
    return render(
        request,
        "marketplace/job_detail.html",
        {
            "job": job,
            "media": job.media.all(),
            "applications_count": job.applications.count(),
        },
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff)
def portal_dashboard_page(request):
    metrics = repository.portal_metrics()
    sections = [
        ("dashboard", "Dashboard"),
        ("users", "Users"),
        ("jobs", "Jobs"),
        ("wallet", "Wallet"),
        ("tickets", "Tickets"),
        ("settings", "Settings"),
    ]
    return render(
        request,
        "portal/dashboard.html",
        {
            "metrics": metrics,
            "sections": sections,
            "categories": MarketplaceCategory.objects.filter(is_active=True)[:10],
            "recent_jobs": repository.public_jobs()[:10],
        },
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff)
def portal_jobs_page(request):
    return portal_dashboard_page(request)


@user_passes_test(lambda user: user.is_authenticated and user.is_staff)
def portal_wallet_page(request):
    return portal_dashboard_page(request)


@user_passes_test(lambda user: user.is_authenticated and user.is_staff)
def portal_support_page(request):
    return portal_dashboard_page(request)


@user_passes_test(lambda user: user.is_authenticated and user.is_staff)
def portal_settings_page(request):
    return portal_dashboard_page(request)

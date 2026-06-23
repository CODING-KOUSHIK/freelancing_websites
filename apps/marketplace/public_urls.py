"""Public marketing pages for the platform."""
from django.urls import path
from apps.marketplace import template_views


urlpatterns = [
    path("about/", template_views.marketing_page, {"slug": "about"}, name="about"),
    path("contact/", template_views.marketing_page, {"slug": "contact"}, name="contact"),
    path("faq/", template_views.marketing_page, {"slug": "faq"}, name="faq"),
    path("blog/", template_views.marketing_page, {"slug": "blog"}, name="blog"),
    path("privacy-policy/", template_views.marketing_page, {"slug": "privacy-policy"}, name="privacy-policy"),
    path("terms/", template_views.marketing_page, {"slug": "terms"}, name="terms"),
    path("careers/", template_views.marketing_page, {"slug": "careers"}, name="careers"),
    path("success-stories/", template_views.marketing_page, {"slug": "success-stories"}, name="success-stories"),
    path("pricing/", template_views.marketing_page, {"slug": "pricing"}, name="pricing"),
    path("referral/", template_views.marketing_page, {"slug": "referral"}, name="referral"),
]

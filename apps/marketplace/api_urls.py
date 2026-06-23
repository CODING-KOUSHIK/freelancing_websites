"""Marketplace API routes."""
from django.urls import path

from apps.marketplace import api_views


urlpatterns = [
    path("categories/", api_views.MarketplaceCategoryListView.as_view(), name="api-marketplace-categories"),
    path("jobs/", api_views.JobListCreateView.as_view(), name="api-marketplace-jobs"),
    path("jobs/<str:job_id>/", api_views.JobDetailView.as_view(), name="api-marketplace-job-detail"),
    path("jobs/<str:job_id>/apply/", api_views.ApplyToJobView.as_view(), name="api-marketplace-job-apply"),
    path("jobs/<str:job_id>/save/", api_views.SavedJobToggleView.as_view(), name="api-marketplace-job-save"),
    path("jobs/<str:job_id>/follow/", api_views.JobFollowToggleView.as_view(), name="api-marketplace-job-follow"),
    path("recruiters/<uuid:recruiter_id>/follow/", api_views.RecruiterFollowToggleView.as_view(), name="api-marketplace-recruiter-follow"),
    path("applications/", api_views.ApplicationListView.as_view(), name="api-marketplace-applications"),
    path("applications/<uuid:pk>/submit/", api_views.SubmitApplicationView.as_view(), name="api-marketplace-submit"),
    path("saved/", api_views.SavedJobListView.as_view(), name="api-marketplace-saved"),
    path("followed-jobs/", api_views.JobFollowListView.as_view(), name="api-marketplace-followed-jobs"),
    path("followed-recruiters/", api_views.RecruiterFollowListView.as_view(), name="api-marketplace-followed-recruiters"),
    path("overview/", api_views.MarketplaceOverviewView.as_view(), name="api-marketplace-overview"),
    path("profile/", api_views.MarketplaceProfileView.as_view(), name="api-marketplace-profile"),
    path("admin/metrics/", api_views.PortalMetricsView.as_view(), name="api-marketplace-portal-metrics"),
    path("settings/", api_views.DynamicSettingListCreateView.as_view(), name="api-marketplace-settings"),
    path("settings/<slug:key>/", api_views.DynamicSettingDetailView.as_view(), name="api-marketplace-setting-detail"),
    path("templates/", api_views.NotificationTemplateListCreateView.as_view(), name="api-marketplace-templates"),
    path("templates/<slug:slug>/", api_views.NotificationTemplateDetailView.as_view(), name="api-marketplace-template-detail"),
    path("snapshots/", api_views.AnalyticsSnapshotListView.as_view(), name="api-marketplace-snapshots"),
]

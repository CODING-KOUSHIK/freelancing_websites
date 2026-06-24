"""Recordings API URLs"""
from django.urls import path
from apps.recordings import views

urlpatterns = [
    # Core session lifecycle
    path("request/", views.SendRecordingRequestView.as_view(), name="api-recording-request"),
    path("<uuid:session_id>/accept/", views.AcceptRecordingRequestView.as_view(), name="api-recording-accept"),
    path("<uuid:session_id>/reject/", views.RejectRecordingRequestView.as_view(), name="api-recording-reject"),
    path("<uuid:session_id>/cancel/", views.CancelSessionView.as_view(), name="api-recording-cancel"),
    path("<uuid:session_id>/start/", views.StartRecordingView.as_view(), name="api-recording-start"),
    path("<uuid:session_id>/end/", views.EndRecordingView.as_view(), name="api-recording-end"),
    path("<uuid:session_id>/chunk/", views.UploadChunkView.as_view(), name="api-recording-chunk"),

    # Partner picker — users approved for the same job who are online
    path("partners/<int:job_id>/", views.AvailablePartnersView.as_view(), name="api-recording-partners"),

    # Stats — success/rejection counts shown in online panel
    path("stats/", views.RecordingStatsView.as_view(), name="api-recording-stats"),

    # File management
    path("<uuid:session_id>/download/", views.DownloadRecordingView.as_view(), name="api-recording-download"),
    path("<uuid:session_id>/delete/", views.DeleteRecordingView.as_view(), name="api-recording-delete"),

    # Library & history
    path("library/", views.RecordingLibraryView.as_view(), name="api-recording-library"),
    path("history/", views.RecordingHistoryView.as_view(), name="api-recording-history"),
    path("<uuid:session_id>/", views.RecordingDetailView.as_view(), name="api-recording-detail"),
]


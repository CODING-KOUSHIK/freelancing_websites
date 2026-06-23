"""Marketplace API endpoints."""
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketplace.models import (
    AnalyticsSnapshot,
    DynamicSetting,
    JobApplication,
    JobFollow,
    JobPosting,
    JobSubmission,
    MarketplaceCategory,
    MarketplaceProfile,
    NotificationTemplate,
    RecruiterFollow,
    SavedJob,
)
from apps.marketplace.permissions import IsStaffOrRecruiter
from apps.marketplace.repositories import MarketplaceRepository
from apps.marketplace.serializers import (
    AnalyticsSnapshotSerializer,
    DynamicSettingSerializer,
    JobApplicationSerializer,
    JobFollowSerializer,
    JobPostingSerializer,
    JobPostingWriteSerializer,
    JobSubmissionSerializer,
    MarketplaceCategorySerializer,
    MarketplaceProfileSerializer,
    NotificationTemplateSerializer,
    RecruiterFollowSerializer,
    SavedJobSerializer,
)
from apps.marketplace.services import MarketplaceService


repository = MarketplaceRepository()
User = get_user_model()


class MarketplaceCategoryListView(generics.ListAPIView):
    serializer_class = MarketplaceCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return repository.categories().annotate(job_count=Count("jobs"))


class JobListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return JobPostingWriteSerializer
        return JobPostingSerializer

    def get_queryset(self):
        qs = repository.public_jobs().annotate(
            saved_count=Count("saved_by", distinct=True),
            follower_count=Count("followers", distinct=True),
        )
        params = self.request.query_params
        category = params.get("category")
        recruiter = params.get("recruiter")
        featured = params.get("featured")
        status_name = params.get("status")
        search = params.get("search")
        if category:
            qs = qs.filter(category__code=category)
        if recruiter:
            qs = qs.filter(recruiter_id=recruiter)
        if featured in {"1", "true", "True"}:
            qs = qs.filter(featured_job=True)
        if status_name:
            qs = qs.filter(status=status_name)
        if search:
            qs = qs.filter(title__icontains=search)
        return qs

    def perform_create(self, serializer):
        job = MarketplaceService.create_or_update_job(
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        self._created_job = job

    def create(self, request, *args, **kwargs):
        if not IsStaffOrRecruiter().has_permission(request, self):
            return Response({"detail": "Recruiter access required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = MarketplaceService.create_or_update_job(
            user=request.user,
            validated_data=serializer.validated_data,
        )
        output = JobPostingSerializer(job, context={"request": request})
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)


class JobDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "job_id"

    def get_serializer_class(self):
        if self.request.method in {"PUT", "PATCH"}:
            return JobPostingWriteSerializer
        return JobPostingSerializer

    def get_queryset(self):
        return repository.job_detail_queryset().annotate(
            saved_count=Count("saved_by", distinct=True),
            follower_count=Count("followers", distinct=True),
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.recruiter_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "You do not own this job."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop("partial", False))
        serializer.is_valid(raise_exception=True)
        job = MarketplaceService.create_or_update_job(
            user=request.user,
            validated_data=serializer.validated_data,
            instance=instance,
        )
        return Response(JobPostingSerializer(job, context={"request": request}).data)


class ApplyToJobView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(JobPosting, job_id=job_id)
        application = MarketplaceService.apply_to_job(
            user=request.user,
            job=job,
            cover_letter=request.data.get("cover_letter", ""),
            expected_rate=request.data.get("expected_rate"),
            payload=request.data.get("payload") or {},
        )
        return Response(JobApplicationSerializer(application, context={"request": request}).data, status=201)


class ApplicationListView(generics.ListAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return JobApplication.objects.select_related("job", "applicant").prefetch_related("submissions")
        return JobApplication.objects.filter(applicant=self.request.user).select_related("job", "applicant").prefetch_related("submissions")


class SubmitApplicationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(JobApplication, pk=pk)
        submission = MarketplaceService.submit_application(
            user=request.user,
            application=application,
            submission_data={
                "submission_type": request.data.get("submission_type", application.job.submission_type),
                "text_content": request.data.get("text_content", ""),
                "external_url": request.data.get("external_url", ""),
                "form_payload": request.data.get("form_payload") or {},
                "file_upload": request.FILES.get("file_upload"),
                "audio_upload": request.FILES.get("audio_upload"),
                "video_upload": request.FILES.get("video_upload"),
                "image_upload": request.FILES.get("image_upload"),
                "payment_amount": request.data.get("payment_amount", 0),
                "submission_note": request.data.get("submission_note", ""),
            },
        )
        return Response(JobSubmissionSerializer(submission, context={"request": request}).data, status=201)


class SavedJobToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(JobPosting, job_id=job_id)
        saved = MarketplaceService.toggle_saved_job(request.user, job)
        return Response({"saved": saved})


class JobFollowToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        job = get_object_or_404(JobPosting, job_id=job_id)
        followed = MarketplaceService.toggle_job_follow(request.user, job)
        return Response({"followed": followed})


class RecruiterFollowToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, recruiter_id):
        recruiter = get_object_or_404(User, pk=recruiter_id)
        followed = MarketplaceService.toggle_recruiter_follow(request.user, recruiter)
        return Response({"followed": followed})


class SavedJobListView(generics.ListAPIView):
    serializer_class = SavedJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user).select_related("job", "job__recruiter", "job__category")


class JobFollowListView(generics.ListAPIView):
    serializer_class = JobFollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JobFollow.objects.filter(user=self.request.user).select_related("job", "job__recruiter", "job__category")


class RecruiterFollowListView(generics.ListAPIView):
    serializer_class = RecruiterFollowSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RecruiterFollow.objects.filter(user=self.request.user).select_related("recruiter")


class MarketplaceOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = MarketplaceService.get_or_create_profile(request.user)
        return Response(
            {
                "profile": MarketplaceProfileSerializer(profile, context={"request": request}).data,
                "jobs": repository.public_jobs().count(),
                "overview": repository.user_overview(request.user),
                "saved_jobs": SavedJob.objects.filter(user=request.user).count(),
                "followed_jobs": JobFollow.objects.filter(user=request.user).count(),
                "followed_recruiters": RecruiterFollow.objects.filter(user=request.user).count(),
            }
        )


class MarketplaceProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MarketplaceProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return MarketplaceService.get_or_create_profile(self.request.user)


class PortalMetricsView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        return Response(repository.portal_metrics())


class DynamicSettingListCreateView(generics.ListCreateAPIView):
    serializer_class = DynamicSettingSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = DynamicSetting.objects.all()
    filterset_fields = ["group", "is_public", "is_editable"]
    search_fields = ["key", "label", "group"]


class DynamicSettingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DynamicSettingSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = DynamicSetting.objects.all()
    lookup_field = "key"


class NotificationTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = NotificationTemplate.objects.all()
    filterset_fields = ["channel", "is_active"]
    search_fields = ["slug", "subject"]


class NotificationTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = NotificationTemplate.objects.all()
    lookup_field = "slug"


class AnalyticsSnapshotListView(generics.ListAPIView):
    serializer_class = AnalyticsSnapshotSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    queryset = AnalyticsSnapshot.objects.all()
    ordering = ["-snapshot_date"]

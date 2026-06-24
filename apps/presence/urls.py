"""Presence API views — Online users, search"""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import path
from apps.accounts.serializers import PublicUserSerializer
from apps.presence.models import UserPresence

User = get_user_model()


class OnlineUsersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = getattr(settings, "MAX_ONLINE_USERS_DISPLAY", 10)
        # ✅ FIXED: Always exclude the requesting user from partner list
        presences = (
            UserPresence.objects
            .filter(is_online=True)
            .exclude(user=request.user)          # Never show yourself
            .select_related("user")
            .order_by("?")[:limit]               # Randomize every refresh
        )
        users = [p.user for p in presences]
        total_online = UserPresence.objects.filter(is_online=True).count()
        serializer = PublicUserSerializer(users, many=True, context={"request": request})
        return Response({
            "count": len(users),
            "total_online": total_online,        # Show total without self
            "users": serializer.data,
        })



class UserSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        online_only = request.query_params.get("online_only", "false").lower() == "true"

        qs = User.objects.filter(is_active=True, is_banned=False).exclude(pk=request.user.pk)

        if query:
            qs = qs.filter(full_name__icontains=query)

        if online_only:
            qs = qs.filter(presence__is_online=True)

        qs = qs.select_related("presence")[:20]
        serializer = PublicUserSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class LeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        category = request.query_params.get("category", "earnings")
        from apps.recordings.models import RecordingSession
        from django.db.models import Q, Sum, Count

        if category == "earnings":
            from apps.wallet.models import Wallet
            top = (
                Wallet.objects
                .filter(user__is_active=True, user__is_banned=False)
                .select_related("user")
                .order_by("-total_earned")[:20]
            )
            users = [w.user for w in top]
        elif category == "recordings":
            from django.db.models import Q
            top = (
                User.objects
                .filter(is_active=True, is_banned=False)
                .annotate(
                    rec_count=Count(
                        "sessions_as_a",
                        filter=Q(sessions_as_a__status="completed"),
                    )
                )
                .order_by("-rec_count")[:20]
            )
            users = list(top)
        else:
            users = User.objects.filter(is_active=True, is_banned=False).order_by("-reputation_score")[:20]

        serializer = PublicUserSerializer(users, many=True, context={"request": request})
        return Response({"category": category, "leaderboard": serializer.data})


urlpatterns = [
    path("online/", OnlineUsersView.as_view(), name="api-online-users"),
    path("search/", UserSearchView.as_view(), name="api-user-search"),
    path("leaderboard/", LeaderboardView.as_view(), name="api-leaderboard"),
]

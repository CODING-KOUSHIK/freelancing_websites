"""Accounts API views — Registration, OTP, Login, Profile, KYC"""
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import EmailOTP, LoginHistory, KYCDocument
from apps.accounts.serializers import (
    RegisterSerializer, VerifyOTPSerializer, UserProfileSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    LoginHistorySerializer, KYCDocumentSerializer,
)
from apps.core.models import AuditLog
from apps.core.email_utils import send_otp_email, send_html_email
from apps.notifications.models import Notification
from apps.wallet.models import Wallet

User = get_user_model()
logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")


def lockout_response(request, credentials, *args, **kwargs):
    from rest_framework.response import Response
    return Response(
        {"error": "Account temporarily locked due to multiple failed login attempts. Try again in 15 minutes."},
        status=429,
    )


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Create wallet
            Wallet.objects.get_or_create(user=user)
            # Generate & send OTP via direct smtplib
            otp = EmailOTP.generate(user, purpose="email_verify")
            send_otp_email(user.email, otp.otp_code, purpose="email_verify")
            AuditLog.objects.create(
                user=user, action="register",
                ip_address=get_client_ip(request),
                description=f"New user registered: {user.email}",
            )
            return Response(
                {
                    "message": "Registration successful. Please check your email for the OTP.",
                    "email": user.email,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            user = data["user"]
            otp = data["otp"]
            otp.is_used = True
            otp.save()

            if data["purpose"] == "email_verify":
                user.is_verified = True
                user.save(update_fields=["is_verified"])
                AuditLog.objects.create(user=user, action="otp_verified", description="Email verified")
                # Check referral bonus
                self._handle_referral(user)
                tokens = self._get_tokens(user)
                return Response({"message": "Email verified successfully.", **tokens})

            return Response({"message": "OTP verified successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}

    def _handle_referral(self, user):
        if user.referred_by:
            from apps.core.models import Referral, SiteSettings
            referral_bonus = float(SiteSettings.get("referral_bonus", "50"))
            ref, created = Referral.objects.get_or_create(
                referrer=user.referred_by,
                referred_user=user,
                defaults={"bonus_amount": referral_bonus},
            )
            if created and not ref.bonus_paid:
                user.referred_by.wallet.credit(
                    amount=referral_bonus,
                    description=f"Referral bonus for {user.email}",
                    transaction_type="referral",
                )
                ref.bonus_paid = True
                ref.bonus_paid_at = timezone.now()
                ref.save()
                Notification.send(
                    user=user.referred_by,
                    notification_type="referral_bonus",
                    title="Referral Bonus! 🎉",
                    message=f"You earned ₹{referral_bonus} as {user.full_name} joined using your referral code!",
                    action_url="/wallet/",
                )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        from rest_framework.exceptions import AuthenticationFailed
        data = super().validate(attrs)
        user = self.user
        if not user.is_verified:
            raise AuthenticationFailed("Please verify your email first.")
        user.update_login_streak()
        req = self.context.get("request")
        LoginHistory.objects.create(
            user=user,
            ip_address=get_client_ip(req) if req else "",
            success=True,
        )
        AuditLog.objects.create(user=user, action="login", description="User logged in via API")
        data["user"] = {
            "id": str(user.pk),
            "email": user.email,
            "full_name": user.full_name,
            "level": user.level,
            "is_verified": user.is_verified,
            "profile_photo": user.profile_photo.url if user.profile_photo else None,
        }
        return data


class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class SessionTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        refresh = RefreshToken.for_user(request.user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(email=serializer.validated_data["email"])
            otp = EmailOTP.generate(user, purpose="password_reset")
            # Send via direct smtplib
            send_otp_email(user.email, otp.otp_code, purpose="password_reset")
            AuditLog.objects.create(user=user, action="password_reset", description="Password reset OTP sent")
            return Response({"message": "OTP sent to your email."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            try:
                user = User.objects.get(email=data["email"])
                otp = EmailOTP.objects.get(
                    user=user, otp_code=data["otp_code"],
                    purpose="password_reset", is_used=False,
                )
                if not otp.is_valid:
                    return Response({"error": "OTP expired."}, status=400)
                user.set_password(data["new_password"])
                user.save()
                otp.is_used = True
                otp.save()
                return Response({"message": "Password reset successfully."})
            except (User.DoesNotExist, EmailOTP.DoesNotExist):
                return Response({"error": "Invalid OTP or email."}, status=400)
        return Response(serializer.errors, status=400)


class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        purpose = request.data.get("purpose", "email_verify")
        try:
            user = User.objects.get(email=email)
            otp = EmailOTP.generate(user, purpose=purpose)
            # Send via direct smtplib
            send_otp_email(user.email, otp.otp_code, purpose=purpose)
            return Response({"message": "OTP resent to your email."})
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)


class LoginHistoryView(generics.ListAPIView):
    serializer_class = LoginHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.request.user.login_history.order_by("-created_at")[:20]


class KYCDocumentView(generics.ListCreateAPIView):
    serializer_class = KYCDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return KYCDocument.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.kyc_status not in ["not_submitted", "rejected"]:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("KYC already submitted or approved.")
        serializer.save(user=user)
        user.kyc_status = "pending"
        user.save(update_fields=["kyc_status"])


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        from apps.recordings.models import RecordingSession
        from django.db.models import Q, Sum, Avg
        from apps.ratings.models import Rating

        sessions = RecordingSession.objects.filter(
            Q(user_a=user) | Q(user_b=user), status="completed"
        )
        total_seconds = sessions.aggregate(t=Sum("duration_seconds"))["t"] or 0

        try:
            wallet = user.wallet
        except Exception:
            wallet = None

        avg = Rating.objects.filter(ratee=user, is_abuse_report=False).aggregate(avg=Avg("score"))["avg"] or 0

        return Response({
            "available_balance": str(wallet.available_balance) if wallet else "0.00",
            "pending_earnings": str(wallet.pending_balance) if wallet else "0.00",
            "total_earnings": str(wallet.total_earned) if wallet else "0.00",
            "completed_recordings": sessions.count(),
            "total_hours": round(total_seconds / 3600, 2),
            "reputation_score": round(avg, 2),
            "profile_completion": user.profile_completion,
            "level": user.level,
            "login_streak": user.login_streak,
            "referral_code": user.referral_code,
            "kyc_status": user.kyc_status,
            "unread_notifications": user.notifications.filter(is_read=False).count(),
        })

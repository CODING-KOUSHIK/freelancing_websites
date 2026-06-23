"""Accounts serializers — Registration, OTP, Profile, Auth"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from apps.accounts.models import EmailOTP, LoginHistory, KYCDocument

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, label="Confirm Password")
    referral_code_used = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "email", "full_name", "password", "password2",
            "gender", "whatsapp_number", "date_of_birth",
            "country", "profile_photo", "referral_code_used",
        ]
        extra_kwargs = {
            "profile_photo": {"required": False},
            "date_of_birth": {"required": False},
        }

    def validate(self, data):
        if data["password"] != data.pop("password2"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        referral_code_used = validated_data.pop("referral_code_used", None)
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
            gender=validated_data.get("gender", ""),
            whatsapp_number=validated_data.get("whatsapp_number", ""),
            date_of_birth=validated_data.get("date_of_birth"),
            country=validated_data.get("country", ""),
            profile_photo=validated_data.get("profile_photo"),
        )
        user.is_active = True
        user.is_verified = False

        if referral_code_used:
            try:
                referrer = User.objects.get(referral_code=referral_code_used)
                user.referred_by = referrer
            except User.DoesNotExist:
                pass

        user.save()
        return user


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=["email_verify", "password_reset", "login"],
        default="email_verify",
    )

    def validate(self, data):
        try:
            user = User.objects.get(email=data["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "User not found."})

        try:
            otp = EmailOTP.objects.get(
                user=user,
                otp_code=data["otp_code"],
                purpose=data["purpose"],
                is_used=False,
            )
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError({"otp_code": "Invalid OTP."})

        if not otp.is_valid:
            raise serializers.ValidationError({"otp_code": "OTP has expired."})

        data["user"] = user
        data["otp"] = otp
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    profile_completion = serializers.ReadOnlyField()
    reputation_score = serializers.ReadOnlyField()
    level = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "gender", "whatsapp_number",
            "date_of_birth", "country", "profile_photo", "bio",
            "level", "reputation_score", "referral_code", "is_verified",
            "is_profile_verified", "kyc_status", "dark_mode",
            "email_notifications", "whatsapp_notifications",
            "auto_accept_requests", "profile_completion",
            "date_joined", "login_streak",
        ]
        read_only_fields = [
            "id", "email", "level", "reputation_score", "referral_code",
            "is_verified", "is_profile_verified", "kyc_status",
            "date_joined", "login_streak",
        ]


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal public profile — for online list, leaderboard."""
    is_online = serializers.SerializerMethodField()
    last_seen = serializers.SerializerMethodField()
    total_recordings = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "full_name", "profile_photo", "country",
            "level", "reputation_score", "is_online", "last_seen",
            "total_recordings",
        ]

    def get_is_online(self, obj):
        try:
            return obj.presence.is_online
        except Exception:
            return False

    def get_last_seen(self, obj):
        try:
            return obj.presence.last_seen_display
        except Exception:
            return "Unknown"

    def get_total_recordings(self, obj):
        from apps.recordings.models import RecordingSession
        from django.db.models import Q
        return RecordingSession.objects.filter(
            Q(user_a=obj) | Q(user_b=obj), status="completed"
        ).count()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account with that email.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(validators=[validate_password])
    new_password2 = serializers.CharField()

    def validate(self, data):
        if data["new_password"] != data["new_password2"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return data


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ["id", "ip_address", "device_type", "location", "success", "created_at"]


class KYCDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCDocument
        fields = ["id", "doc_type", "document_front", "document_back", "doc_number", "status", "created_at"]
        read_only_fields = ["status"]

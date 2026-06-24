"""Accounts template views — render HTML pages + handle Django session auth"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "accounts/landing.html")


def login_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user:
            if not user.is_verified:
                return render(request, "accounts/login.html", {
                    "error": "Please verify your email first. Check your inbox for the OTP."
                })
            login(request, user)
            user.update_login_streak()
            next_url = request.GET.get("next", "/dashboard/")
            return redirect(next_url)
        return render(request, "accounts/login.html", {"error": "Invalid email or password."})
    return render(request, "accounts/login.html")


def register_page(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "accounts/register.html")


def verify_email_page(request):
    return render(request, "accounts/verify_email.html")


def forgot_password_page(request):
    return render(request, "accounts/forgot_password.html")


@login_required
def profile_page(request):
    return render(request, "accounts/profile.html")


def logout_view(request):
    logout(request)
    return redirect("/")


@csrf_exempt
@require_POST
def session_login(request):
    """
    Creates a Django session after successful JWT login.
    Called from JS after /api/auth/login/ succeeds.
    """
    try:
        data = json.loads(request.body)
        email = data.get("email", "")
        password = data.get("password", "")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user = authenticate(request, username=email, password=password)
    if user:
        if not user.is_verified:
            return JsonResponse({"error": "Email not verified."}, status=403)
        login(request, user)
        user.update_login_streak()
        return JsonResponse({"ok": True, "redirect": "/dashboard/"})
    return JsonResponse({"error": "Invalid credentials."}, status=401)


@csrf_exempt
@require_POST
def session_login_after_otp(request):
    """
    Creates a Django session after successful OTP verification.
    """
    try:
        data = json.loads(request.body)
        email = data.get("email", "")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(email=email, is_verified=True)
        login(request, user)
        return JsonResponse({"ok": True})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found or not verified."}, status=404)


@login_required
def invite_page(request):
    """Referral / invite page with share link and stats."""
    from django.conf import settings
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    referral_url = f"{site_url}/invite/{request.user.referral_code}/"

    message = f"Join me on VoiceMarket and earn money by recording your voice! Use my link: {referral_url}"

    context = {
        "referral_url": referral_url,
        "referral_code": request.user.referral_code,
        "whatsapp_url": f"https://wa.me/?text={message}",
        "telegram_url": f"https://t.me/share/url?url={referral_url}&text={message}",
        "facebook_url": f"https://www.facebook.com/sharer/sharer.php?u={referral_url}",
        "email_url": f"mailto:?subject=Join VoiceMarket — Earn Money Recording Voice&body={message}",
        "total_referrals": request.user.referrals.count(),
        "active_referrals": request.user.referrals.filter(is_active=True).count(),
        "referral_balance": request.user.wallet.referral_balance if hasattr(request.user, "wallet") else 0,
    }
    return render(request, "accounts/invite.html", context)


def referral_signup_redirect(request, code):
    """
    Redirect to register page with referral code pre-filled.
    Stores the code in session so it's applied on registration.
    """
    request.session["referral_code"] = code
    return redirect("/register/?ref=" + code)


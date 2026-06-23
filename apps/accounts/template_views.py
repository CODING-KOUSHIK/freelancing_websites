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

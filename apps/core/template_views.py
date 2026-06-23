"""Core template views — dashboard, leaderboard"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard_page(request):
    context = {
        "levels": [
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("expert", "Expert"),
            ("verified_expert", "Verified Expert"),
        ]
    }
    return render(request, "dashboard/index.html", context)


@login_required
def leaderboard_page(request):
    return render(request, "leaderboard/index.html")

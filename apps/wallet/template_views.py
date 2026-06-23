"""Wallet template views"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def wallet_page(request):
    return render(request, "wallet/index.html")


@login_required
def withdraw_page(request):
    return render(request, "wallet/withdraw.html")

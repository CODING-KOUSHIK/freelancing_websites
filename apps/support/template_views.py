"""Support template views"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.support.models import SupportTicket


@login_required
def tickets_page(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "support/tickets.html", {"tickets": tickets})


@login_required
def ticket_detail_page(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk, user=request.user)
    return render(request, "support/ticket_detail.html", {"ticket": ticket})

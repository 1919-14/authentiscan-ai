from django.conf import settings
from django.shortcuts import render

from detector.models import ScanResult


def landing(request):
    """Marketing / landing page — the front door of the app."""
    stats = {
        "total_scans": ScanResult.objects.count(),
        "flagged_scans": ScanResult.objects.filter(ai_likelihood__gte=60).count(),
    }
    return render(request, "core/landing.html", {"stats": stats})


def about(request):
    """Explains the forensic technique (ELA + metadata heuristics) in plain terms."""
    return render(request, "core/about.html")


def contributors(request):
    """Team / contributors page for the college submission."""
    return render(
        request,
        "core/contributors.html",
        {"contributors": settings.CONTRIBUTORS},
    )

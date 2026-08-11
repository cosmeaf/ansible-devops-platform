"""Platform management screens.

This is the platform's own interface, governed by roles. It never links to
or depends on Django Admin, which stays an operator-only backdoor
(see docs/adr/0012-admin-is-not-product-surface.md).

Server-rendered because the Next.js client is Module 2; the access rules
enforced here are the same ones that module will consume over the API.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_GET

from audit.models import AuditEvent
from ipintel.models import IPIntelligence
from security.models import SecurityEvent
from settings_platform.models import PlatformSetting

from .models import Role, UserRole, roles_for

PAGE_SIZE = 25


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


@login_required
@require_GET
def overview(request):
    """Landing page for the management area."""
    return render(
        request,
        "manage/overview.html",
        {
            "section": "overview",
            "counts": {
                "audit": AuditEvent.objects.count(),
                "security": SecurityEvent.objects.count(),
                "ipintel": IPIntelligence.objects.count(),
                "settings": PlatformSetting.objects.count(),
                "users": get_user_model().objects.count(),
                "roles": Role.objects.count(),
            },
            "my_roles": roles_for(request.user),
            "recent": AuditEvent.objects.all()[:8],
        },
    )


@login_required
@permission_required("audit.view_auditevent", raise_exception=True)
@require_GET
def audit_events(request):
    events = AuditEvent.objects.select_related("user")
    if q := request.GET.get("q", "").strip():
        events = events.filter(username_snapshot__icontains=q)
    return render(
        request,
        "manage/audit.html",
        {"section": "audit", "page": _page(request, events), "q": q},
    )


@login_required
@permission_required("security.view_securityevent", raise_exception=True)
@require_GET
def security_events(request):
    return render(
        request,
        "manage/security.html",
        {
            "section": "security",
            "page": _page(request, SecurityEvent.objects.select_related("user")),
        },
    )


@login_required
@permission_required("ipintel.view_ipintelligence", raise_exception=True)
@require_GET
def ip_intelligence(request):
    return render(
        request,
        "manage/ipintel.html",
        {"section": "ipintel", "page": _page(request, IPIntelligence.objects.all())},
    )


@login_required
@permission_required("settings_platform.view_platformsetting", raise_exception=True)
@require_GET
def platform_settings(request):
    return render(
        request,
        "manage/settings.html",
        {"section": "settings", "page": _page(request, PlatformSetting.objects.all())},
    )


@login_required
@permission_required("auth.view_user", raise_exception=True)
@require_GET
def users(request):
    people = get_user_model().objects.prefetch_related("user_roles__role").order_by("username")
    return render(
        request,
        "manage/users.html",
        {"section": "users", "page": _page(request, people)},
    )


@login_required
@permission_required("authentication.view_role", raise_exception=True)
@require_GET
def roles(request):
    return render(
        request,
        "manage/roles.html",
        {
            "section": "roles",
            "roles": Role.objects.prefetch_related("permissions").all(),
            "assignments": UserRole.objects.select_related("user", "role")[:50],
        },
    )

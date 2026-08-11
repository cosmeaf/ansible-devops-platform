"""Ansible infrastructure management screens.

This is product surface: the interface for managing what Ansible acts on.
Platform internals (audit, security, users, roles) live in Django Admin —
see docs/adr/0012-admin-is-not-product-surface.md.
"""

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import Environment, Server, ServerGroup, ServerStatus

PAGE_SIZE = 25


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


@login_required
@require_GET
def overview(request):
    """Ansible management landing page."""
    servers = Server.objects.filter(active=True)
    return render(
        request,
        "manage/overview.html",
        {
            "section": "overview",
            "counts": {
                "servers": servers.count(),
                "environments": Environment.objects.filter(active=True).count(),
                "groups": ServerGroup.objects.count(),
                "online": servers.filter(status=ServerStatus.ONLINE).count(),
                "untested": servers.filter(status=ServerStatus.UNKNOWN).count(),
                "failing": servers.filter(
                    status__in=[ServerStatus.OFFLINE, ServerStatus.ERROR]
                ).count(),
            },
            "recent_servers": servers.select_related("environment")[:8],
        },
    )


@login_required
@permission_required("infrastructure.view_server", raise_exception=True)
@require_GET
def servers(request):
    queryset = Server.objects.select_related("environment").prefetch_related("groups")

    if q := request.GET.get("q", "").strip():
        queryset = queryset.filter(name__icontains=q)
    if env := request.GET.get("environment", "").strip():
        queryset = queryset.filter(environment__slug=env)
    if status := request.GET.get("status", "").strip():
        queryset = queryset.filter(status=status)

    return render(
        request,
        "manage/servers.html",
        {
            "section": "servers",
            "page": _page(request, queryset),
            "q": q,
            "environments": Environment.objects.filter(active=True),
            "statuses": ServerStatus.choices,
            "selected_environment": env,
            "selected_status": status,
        },
    )


@login_required
@permission_required("infrastructure.view_server", raise_exception=True)
@require_GET
def server_detail(request, uuid):
    server = get_object_or_404(
        Server.objects.select_related("environment").prefetch_related("groups"), uuid=uuid
    )
    return render(
        request,
        "manage/server_detail.html",
        {"section": "servers", "server": server},
    )


@login_required
@permission_required("infrastructure.view_environment", raise_exception=True)
@require_GET
def environments(request):
    queryset = Environment.objects.annotate(server_total=Count("servers")).order_by("name")
    return render(
        request,
        "manage/environments.html",
        {"section": "environments", "page": _page(request, queryset)},
    )


@login_required
@permission_required("infrastructure.view_servergroup", raise_exception=True)
@require_GET
def groups(request):
    queryset = ServerGroup.objects.annotate(server_total=Count("servers")).order_by("name")
    return render(
        request,
        "manage/groups.html",
        {"section": "groups", "page": _page(request, queryset)},
    )

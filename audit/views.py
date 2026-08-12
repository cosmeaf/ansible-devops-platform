"""Reading the audit trail.

Recording an action nobody can look at answers no question. This is the
screen that answers "who deleted that, and when" without anyone needing
database access.

Read-only by construction: there is no view here that writes, and the model
has no edit path. A trail that can be edited is not a trail.
"""

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import AuditAction, AuditEvent, AuditResult

PAGE_SIZE = 50


@login_required
@permission_required("audit.view_auditevent", raise_exception=True)
@require_GET
def trail(request):
    queryset = AuditEvent.objects.select_related("user")

    filters = {
        "module": request.GET.get("module", "").strip(),
        "action": request.GET.get("action", "").strip(),
        "result": request.GET.get("result", "").strip(),
        "username": request.GET.get("username", "").strip(),
        "resource": request.GET.get("resource", "").strip(),
    }
    if filters["module"]:
        queryset = queryset.filter(module=filters["module"])
    if filters["action"]:
        queryset = queryset.filter(action=filters["action"])
    if filters["result"]:
        queryset = queryset.filter(result=filters["result"])
    if filters["username"]:
        queryset = queryset.filter(username_snapshot=filters["username"])
    if filters["resource"]:
        # Matches either what was touched or its identifier, because someone
        # looking for "web01" does not know which column it lives in.
        queryset = queryset.filter(resource_id__icontains=filters["resource"])

    return render(
        request,
        "manage/audit.html",
        {
            "section": "audit",
            "page": Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page")),
            "filters": filters,
            "modules": (
                AuditEvent.objects.values_list("module", flat=True).distinct().order_by("module")
            ),
            "actions": AuditAction.choices,
            "results": AuditResult.choices,
            "usernames": (
                AuditEvent.objects.exclude(username_snapshot="")
                .values_list("username_snapshot", flat=True)
                .distinct()
                .order_by("username_snapshot")
            ),
        },
    )


@login_required
@permission_required("audit.view_auditevent", raise_exception=True)
@require_GET
def event(request, uuid):
    """One event in full, including what the value was before and after."""
    record = get_object_or_404(AuditEvent.objects.select_related("user"), uuid=uuid)

    related = AuditEvent.objects.filter(
        resource_type=record.resource_type, resource_id=record.resource_id
    ).exclude(pk=record.pk)[:20]

    return render(
        request,
        "manage/audit_event.html",
        {"section": "audit", "event": record, "related": related},
    )


def history_for(instance, *, limit: int = 10):
    """Every recorded action against *instance*, newest first.

    Used by the object pages, so the trail is where the object is rather than
    only in a separate screen.
    """
    return AuditEvent.objects.select_related("user").filter(
        resource_type=instance.__class__.__name__,
        resource_id=str(getattr(instance, "uuid", "") or instance.pk),
    )[:limit]

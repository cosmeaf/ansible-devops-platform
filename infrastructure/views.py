"""Ansible infrastructure management screens.

This is product surface: the interface for managing what Ansible acts on.
Platform internals (audit, security, users, roles) live in Django Admin —
see docs/adr/0012-admin-is-not-product-surface.md.

Writes here are audited exactly as the API writes are, so an action taken in
the UI is indistinguishable in the trail from the same action over REST.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from audit.models import AuditAction, AuditEvent, AuditResult
from credentials.models import Credential

from .forms import (
    ClientForm,
    CredentialForm,
    EnvironmentForm,
    ServerForm,
    ServerGroupForm,
)
from .models import Client, Environment, Server, ServerGroup, ServerStatus

PAGE_SIZE = 25


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # Left-most entry is the original client; the rest are proxies.
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _audit(request, action, instance, *, module, new=None):
    user = request.user if request.user.is_authenticated else None
    AuditEvent.objects.create(
        user=user,
        username_snapshot=user.get_username() if user else "",
        request_id=getattr(request, "request_id", "") or "",
        session_id=request.session.session_key or "",
        source_ip=_client_ip(request),
        module=module,
        resource_type=instance.__class__.__name__,
        resource_id=str(getattr(instance, "uuid", "") or instance.pk),
        action=action,
        new_value=new,
        result=AuditResult.SUCCESS,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


def _crud(request, *, form_class, instance, module, redirect_to, title, subtitle):
    """Shared create/edit handler for the management forms."""
    creating = instance.pk is None

    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            if creating and hasattr(obj, "created_by") and obj.created_by is None:
                obj.created_by = request.user
            obj.save()
            form.save_m2m()
            _audit(
                request,
                AuditAction.CREATE if creating else AuditAction.UPDATE,
                obj,
                module=module,
                new={"name": str(obj)},
            )
            messages.success(request, f"{obj} {'created' if creating else 'saved'}.")
            return redirect(redirect_to)
    else:
        form = form_class(instance=instance)

    return render(
        request,
        "manage/form.html",
        {
            "form": form,
            "title": title,
            "subtitle": subtitle,
            "cancel_url": reverse(redirect_to),
            "creating": creating,
        },
    )


def _delete(request, *, instance, module, redirect_to, what, blocked_by=""):
    """Shared delete handler, with a confirmation step.

    A deletion nobody confirmed is a deletion nobody meant, so GET renders the
    confirmation and only POST removes anything.
    """
    label = str(instance)

    if request.method == "POST":
        try:
            instance.delete()
        except ProtectedError:
            messages.error(
                request,
                f"{label} still has servers attached. Reassign them before deleting it.",
            )
            return redirect(redirect_to)

        # delete() clears the primary key but leaves the UUID, which is what
        # the trail records — an audit entry that cannot name what it removed
        # would be worthless.
        _audit(request, AuditAction.DELETE, instance, module=module, new={"name": label})
        messages.success(request, f"{label} deleted.")
        return redirect(redirect_to)

    return render(
        request,
        "manage/confirm_delete.html",
        {
            "what": what,
            "label": label,
            "blocked_by": blocked_by,
            "cancel_url": reverse(redirect_to),
        },
    )


# --- read screens ---------------------------------------------------------


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
                "clients": Client.objects.filter(active=True).count(),
                "credentials": Credential.objects.count(),
                "online": servers.filter(status=ServerStatus.ONLINE).count(),
                "untested": servers.filter(status=ServerStatus.UNKNOWN).count(),
            },
            "recent_servers": servers.select_related("environment", "client")[:8],
        },
    )


@login_required
@permission_required("infrastructure.view_server", raise_exception=True)
@require_GET
def servers(request):
    queryset = Server.objects.select_related("environment", "client").prefetch_related("groups")

    if q := request.GET.get("q", "").strip():
        queryset = queryset.filter(name__icontains=q)
    if env := request.GET.get("environment", "").strip():
        queryset = queryset.filter(environment__slug=env)
    if status := request.GET.get("status", "").strip():
        queryset = queryset.filter(status=status)
    if client := request.GET.get("client", "").strip():
        queryset = queryset.filter(client__slug=client)

    return render(
        request,
        "manage/servers.html",
        {
            "section": "servers",
            "page": _page(request, queryset),
            "q": q,
            "environments": Environment.objects.filter(active=True),
            "clients": Client.objects.filter(active=True),
            "statuses": ServerStatus.choices,
            "selected_environment": env,
            "selected_status": status,
            "selected_client": client,
        },
    )


@login_required
@permission_required("infrastructure.view_server", raise_exception=True)
@require_GET
def server_detail(request, uuid):
    server = get_object_or_404(
        Server.objects.select_related("environment", "client", "credential").prefetch_related(
            "groups"
        ),
        uuid=uuid,
    )
    return render(request, "manage/server_detail.html", {"section": "servers", "server": server})


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
        request, "manage/groups.html", {"section": "groups", "page": _page(request, queryset)}
    )


@login_required
@permission_required("infrastructure.view_client", raise_exception=True)
@require_GET
def clients(request):
    queryset = Client.objects.annotate(server_total=Count("servers")).order_by("name")
    return render(
        request, "manage/clients.html", {"section": "clients", "page": _page(request, queryset)}
    )


@login_required
@permission_required("credentials.view_credential", raise_exception=True)
@require_GET
def credential_list(request):
    return render(
        request,
        "manage/credentials.html",
        {"section": "credentials", "page": _page(request, Credential.objects.all())},
    )


# --- write screens --------------------------------------------------------


@login_required
@permission_required("infrastructure.add_server", raise_exception=True)
def server_create(request):
    return _crud(
        request,
        form_class=ServerForm,
        instance=Server(),
        module="infrastructure",
        redirect_to="manage:servers",
        title="Register a server",
        subtitle="A host for Ansible to manage. It becomes an inventory entry.",
    )


@login_required
@permission_required("infrastructure.change_server", raise_exception=True)
def server_edit(request, uuid):
    return _crud(
        request,
        form_class=ServerForm,
        instance=get_object_or_404(Server, uuid=uuid),
        module="infrastructure",
        redirect_to="manage:servers",
        title="Edit server",
        subtitle="Changes apply the next time an inventory is generated.",
    )


@login_required
@permission_required("infrastructure.add_servergroup", raise_exception=True)
def group_create(request):
    return _crud(
        request,
        form_class=ServerGroupForm,
        instance=ServerGroup(),
        module="infrastructure",
        redirect_to="manage:groups",
        title="Create a group",
        subtitle="Becomes an Ansible inventory group.",
    )


@login_required
@permission_required("infrastructure.add_environment", raise_exception=True)
def environment_create(request):
    return _crud(
        request,
        form_class=EnvironmentForm,
        instance=Environment(),
        module="infrastructure",
        redirect_to="manage:environments",
        title="Create an environment",
        subtitle="A deployment tier. It can force check mode on every job.",
    )


@login_required
@permission_required("infrastructure.add_client", raise_exception=True)
def client_create(request):
    return _crud(
        request,
        form_class=ClientForm,
        instance=Client(),
        module="infrastructure",
        redirect_to="manage:clients",
        title="Create a client",
        subtitle="The customer or business unit that owns a set of servers.",
    )


@login_required
@permission_required("credentials.add_credential", raise_exception=True)
def credential_create(request):
    return _crud(
        request,
        form_class=CredentialForm,
        instance=Credential(),
        module="credentials",
        redirect_to="manage:credentials",
        title="Add a credential",
        subtitle="Encrypted at rest. The secret can never be read back.",
    )


@login_required
@permission_required("infrastructure.change_servergroup", raise_exception=True)
def group_edit(request, uuid):
    return _crud(
        request,
        form_class=ServerGroupForm,
        instance=get_object_or_404(ServerGroup, uuid=uuid),
        module="infrastructure",
        redirect_to="manage:groups",
        title="Edit group",
        subtitle="Renaming a group renames the Ansible inventory group.",
    )


@login_required
@permission_required("infrastructure.change_environment", raise_exception=True)
def environment_edit(request, uuid):
    return _crud(
        request,
        form_class=EnvironmentForm,
        instance=get_object_or_404(Environment, uuid=uuid),
        module="infrastructure",
        redirect_to="manage:environments",
        title="Edit environment",
        subtitle="A deployment tier. It can force check mode on every job.",
    )


@login_required
@permission_required("infrastructure.change_client", raise_exception=True)
def client_edit(request, uuid):
    return _crud(
        request,
        form_class=ClientForm,
        instance=get_object_or_404(Client, uuid=uuid),
        module="infrastructure",
        redirect_to="manage:clients",
        title="Edit client",
        subtitle="The customer or business unit that owns a set of servers.",
    )


@login_required
@permission_required("credentials.change_credential", raise_exception=True)
def credential_edit(request, uuid):
    return _crud(
        request,
        form_class=CredentialForm,
        instance=get_object_or_404(Credential, uuid=uuid),
        module="credentials",
        redirect_to="manage:credentials",
        title="Edit credential",
        subtitle="Leave the secret blank to keep the one already stored.",
    )


# --- delete screens -------------------------------------------------------


@login_required
@permission_required("infrastructure.delete_server", raise_exception=True)
def server_delete(request, uuid):
    return _delete(
        request,
        instance=get_object_or_404(Server, uuid=uuid),
        module="infrastructure",
        redirect_to="manage:servers",
        what="server",
        blocked_by="It disappears from every generated inventory.",
    )


@login_required
@permission_required("infrastructure.delete_servergroup", raise_exception=True)
def group_delete(request, uuid):
    group = get_object_or_404(ServerGroup, uuid=uuid)
    return _delete(
        request,
        instance=group,
        module="infrastructure",
        redirect_to="manage:groups",
        what="group",
        blocked_by=_members(group.servers.count(), "keep their registration"),
    )


@login_required
@permission_required("infrastructure.delete_environment", raise_exception=True)
def environment_delete(request, uuid):
    environment = get_object_or_404(Environment, uuid=uuid)
    return _delete(
        request,
        instance=environment,
        module="infrastructure",
        redirect_to="manage:environments",
        what="environment",
        blocked_by=_members(environment.servers.count(), "must be reassigned first"),
    )


@login_required
@permission_required("infrastructure.delete_client", raise_exception=True)
def client_delete(request, uuid):
    client = get_object_or_404(Client, uuid=uuid)
    return _delete(
        request,
        instance=client,
        module="infrastructure",
        redirect_to="manage:clients",
        what="client",
        blocked_by=_members(client.servers.count(), "must be reassigned first"),
    )


@login_required
@permission_required("credentials.delete_credential", raise_exception=True)
def credential_delete(request, uuid):
    credential = get_object_or_404(Credential, uuid=uuid)
    return _delete(
        request,
        instance=credential,
        module="credentials",
        redirect_to="manage:credentials",
        what="credential",
        blocked_by=_members(credential.servers.count(), "will be left without a credential"),
    )


def _members(count: int, consequence: str) -> str:
    """Say what happens to the servers attached, so the warning is specific."""
    if not count:
        return ""
    return f"{count} server{'s' if count != 1 else ''} {consequence}."

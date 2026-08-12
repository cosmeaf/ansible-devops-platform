"""Launching runs and reading what they did."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from audit.models import AuditAction, AuditEvent, AuditResult
from automation.known_hosts import ScanFailed, forget, is_trusted, scan, trust
from infrastructure.models import Server

from .forms import RunPlaybookForm
from .models import Job, JobKind, JobStatus
from .tasks import check_connection, run_job

PAGE_SIZE = 25


def _audit(request, action, job, *, extra=None):
    user = request.user
    AuditEvent.objects.create(
        user=user if user.is_authenticated else None,
        username_snapshot=user.get_username() if user.is_authenticated else "",
        request_id=getattr(request, "request_id", "") or "",
        session_id=request.session.session_key or "",
        source_ip=request.META.get("REMOTE_ADDR") or None,
        module="jobs",
        resource_type="Job",
        resource_id=str(job.uuid),
        action=action,
        new_value={"job": job.label, "check_mode": job.check_mode, **(extra or {})},
        result=AuditResult.SUCCESS,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


@login_required
@permission_required("jobs.view_job", raise_exception=True)
@require_GET
def job_list(request):
    queryset = Job.objects.select_related("environment", "client", "requested_by")
    if status := request.GET.get("status", "").strip():
        queryset = queryset.filter(status=status)

    return render(
        request,
        "manage/jobs.html",
        {
            "section": "jobs",
            "page": Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page")),
            "statuses": JobStatus.choices,
            "selected_status": status,
        },
    )


@login_required
@permission_required("jobs.view_job", raise_exception=True)
@require_GET
def job_detail(request, uuid):
    job = get_object_or_404(
        Job.objects.select_related("environment", "client", "credential", "requested_by"), uuid=uuid
    )
    return render(request, "manage/job_detail.html", {"section": "jobs", "job": job})


@login_required
@permission_required("jobs.view_job", raise_exception=True)
@require_GET
def job_status(request, uuid):
    """Just the state, for a page that is watching a run in progress."""
    job = get_object_or_404(Job, uuid=uuid)
    return JsonResponse(
        {
            "status": job.status,
            "label": job.get_status_display(),
            "finished": job.finished,
            "exit_code": job.exit_code,
            "output": job.output,
            "recap": job.recap,
        }
    )


@login_required
@permission_required("jobs.add_job", raise_exception=True)
def job_create(request):
    if request.method == "POST":
        form = RunPlaybookForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.kind = JobKind.PLAYBOOK
            job.extra_vars = form.cleaned_data["extra_vars_text"]
            job.requested_by = request.user
            job.status = JobStatus.QUEUED
            job.save()
            job.servers.set(form.selected_servers(form.cleaned_data))

            _audit(
                request,
                AuditAction.CHECK if job.check_mode else AuditAction.EXECUTE,
                job,
                extra={"servers": job.servers.count()},
            )
            run_job.delay(str(job.uuid))
            messages.success(request, f"{job.label} queued against {job.servers.count()} servers.")
            return redirect("jobs:detail", uuid=job.uuid)
    else:
        form = RunPlaybookForm(initial={"check_mode": True})

    return render(request, "manage/job_run.html", {"section": "jobs", "form": form})


@login_required
@permission_required("infrastructure.change_server", raise_exception=True)
def server_trust(request, uuid):
    """Show the host key a server offers, and record the decision to accept it.

    Ansible will not connect to a host whose key it has never seen, and that
    refusal is the protection working. Someone still has to look at the
    fingerprint and say yes, which is what this screen is for.
    """
    server = get_object_or_404(Server, uuid=uuid)

    try:
        keys = scan(server.ansible_host, server.ssh_port)
    except ScanFailed as error:
        messages.error(request, str(error))
        return redirect("manage:server-detail", uuid=server.uuid)

    if request.method == "POST":
        added = trust(keys)
        AuditEvent.objects.create(
            user=request.user,
            username_snapshot=request.user.get_username(),
            request_id=getattr(request, "request_id", "") or "",
            session_id=request.session.session_key or "",
            source_ip=request.META.get("REMOTE_ADDR") or None,
            module="automation",
            resource_type="Server",
            resource_id=str(server.uuid),
            action=AuditAction.UPDATE,
            new_value={
                "trusted_host_key": server.ansible_host,
                "fingerprints": [key.label for key in keys],
            },
            result=AuditResult.SUCCESS,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        messages.success(
            request,
            f"Host key accepted for {server.name}."
            if added
            else f"{server.name} was already trusted.",
        )
        return redirect("manage:server-detail", uuid=server.uuid)

    return render(
        request,
        "manage/trust_host_key.html",
        {"section": "servers", "server": server, "keys": keys},
    )


@login_required
@permission_required("infrastructure.change_server", raise_exception=True)
@require_POST
def server_forget(request, uuid):
    """Drop a host key, so the next run refuses until it is accepted again."""
    server = get_object_or_404(Server, uuid=uuid)
    removed = forget(server.ansible_host, server.ssh_port)
    messages.success(
        request,
        f"Host key forgotten for {server.name}."
        if removed
        else f"{server.name} had no trusted key.",
    )
    return redirect("manage:server-detail", uuid=server.uuid)


@login_required
@permission_required("infrastructure.change_server", raise_exception=True)
@require_POST
def server_test(request, uuid):
    """Queue a connection test for one server."""
    server = get_object_or_404(Server, uuid=uuid)

    if not is_trusted(server.ansible_host, server.ssh_port):
        messages.error(
            request,
            f"{server.name} has no accepted host key, so Ansible would refuse to "
            "connect. Review its fingerprint first.",
        )
        return redirect("jobs:server-trust", uuid=server.uuid)

    job = Job.objects.create(
        kind=JobKind.CONNECTION_TEST,
        environment=server.environment,
        client=server.client,
        credential=server.credential,
        requested_by=request.user,
        status=JobStatus.QUEUED,
    )
    job.servers.set([server])

    _audit(request, AuditAction.CHECK, job, extra={"server": server.name})
    check_connection.delay(str(job.uuid))
    messages.success(request, f"Testing the connection to {server.name}.")
    return redirect("jobs:detail", uuid=job.uuid)

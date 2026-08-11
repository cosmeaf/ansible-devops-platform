"""Editing Ansible playbooks from the browser.

What you edit here is a file in the workspace. The editor validates before it
writes, so a file that stops Ansible loading never reaches disk, and every
write is audited the same way a change through the API would be.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from audit.models import AuditAction, AuditEvent, AuditResult

from .forms import PlaybookForm
from .workspace import (
    STARTER_PLAYBOOK,
    UnsafePath,
    delete_playbook,
    list_playbooks,
    read_playbook,
    root,
    validate,
    write_playbook,
)


def _audit(request, action, name, *, result=AuditResult.SUCCESS):
    user = request.user
    AuditEvent.objects.create(
        user=user if user.is_authenticated else None,
        username_snapshot=user.get_username() if user.is_authenticated else "",
        request_id=getattr(request, "request_id", "") or "",
        session_id=request.session.session_key or "",
        source_ip=request.META.get("REMOTE_ADDR") or None,
        module="automation",
        resource_type="Playbook",
        resource_id=name,
        action=action,
        new_value={"playbook": name},
        result=result,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


@login_required
@permission_required("automation.view_playbook", raise_exception=True)
@require_GET
def playbooks(request):
    return render(
        request,
        "manage/playbooks.html",
        {
            "section": "playbooks",
            "playbooks": list_playbooks(),
            "workspace": root(),
        },
    )


@login_required
@permission_required("automation.add_playbook", raise_exception=True)
def playbook_create(request):
    if request.method == "POST":
        form = PlaybookForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            write_playbook(name, form.cleaned_data["content"])
            _audit(request, AuditAction.CREATE, name)
            messages.success(request, f"{name} saved.")
            return redirect("automation:playbook-edit", name=name)
    else:
        form = PlaybookForm(initial={"content": STARTER_PLAYBOOK.format(title="Describe the play")})

    return _editor(request, form, title="New playbook", name="")


@login_required
@permission_required("automation.change_playbook", raise_exception=True)
def playbook_edit(request, name):
    try:
        current = read_playbook(name)
    except UnsafePath:
        messages.error(request, "That is not a path inside the workspace.")
        return redirect("automation:playbooks")
    except (FileNotFoundError, IsADirectoryError):
        messages.error(request, f"No playbook called {name}.")
        return redirect("automation:playbooks")

    if request.method == "POST":
        form = PlaybookForm(request.POST, editing=name)
        if form.is_valid():
            write_playbook(name, form.cleaned_data["content"])
            _audit(request, AuditAction.UPDATE, name)
            messages.success(request, f"{name} saved.")
            return redirect("automation:playbook-edit", name=name)
    else:
        form = PlaybookForm(initial={"name": name, "content": current}, editing=name)

    return _editor(request, form, title=name, name=name)


@login_required
@permission_required("automation.delete_playbook", raise_exception=True)
def playbook_delete(request, name):
    if request.method == "POST":
        try:
            delete_playbook(name)
        except UnsafePath:
            messages.error(request, "That is not a path inside the workspace.")
            return redirect("automation:playbooks")
        except FileNotFoundError:
            messages.error(request, f"No playbook called {name}.")
            return redirect("automation:playbooks")

        _audit(request, AuditAction.DELETE, name)
        messages.success(request, f"{name} deleted.")
        return redirect("automation:playbooks")

    return render(
        request,
        "manage/confirm_delete.html",
        {
            "what": "playbook",
            "label": name,
            "blocked_by": "The file is removed from the workspace on disk.",
            "cancel_url": reverse("automation:playbooks"),
        },
    )


def _editor(request, form, *, title, name):
    """Render the editor, showing validation problems where they belong."""
    return render(
        request,
        "manage/playbook_edit.html",
        {
            "section": "playbooks",
            "form": form,
            "title": title,
            "name": name,
            "problems": validate(form.data.get("content", "")) if request.method == "POST" else [],
        },
    )

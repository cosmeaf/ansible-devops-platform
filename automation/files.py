"""The workspace as a file explorer.

The point of comparison is an editor with the project open: a tree on the
left, a file in the middle, and the ability to create, rename and delete both
files and folders. Anything that changes disk is recorded in the audit trail
with the person who did it, because "who deleted roles/nginx" is a question
someone will eventually ask.
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from audit.models import AuditAction, AuditEvent, AuditResult

from . import workspace
from .forms import FileForm, NewFolderForm, RenameForm
from .workspace import NotEditable, UnsafePath


def _audit(request, action, path, *, detail=None, previous=None):
    user = request.user
    AuditEvent.objects.create(
        user=user if user.is_authenticated else None,
        username_snapshot=user.get_username() if user.is_authenticated else "",
        request_id=getattr(request, "request_id", "") or "",
        session_id=request.session.session_key or "",
        source_ip=request.META.get("REMOTE_ADDR") or None,
        module="automation",
        resource_type="WorkspaceFile",
        resource_id=path,
        action=action,
        previous_value=previous,
        new_value={"path": path, **(detail or {})},
        result=AuditResult.SUCCESS,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


def _parent_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _url_for(route: str, path: str) -> str:
    """Build a workspace URL with the path encoded.

    A path holding & or # would otherwise cut the querystring short and send
    the browser somewhere nobody asked for.
    """
    base = reverse(route)
    return f"{base}?{urlencode({'path': path})}" if path else base


def _back_to(path: str) -> str:
    return _url_for("automation:browse", path)


@login_required
@permission_required("automation.view_playbook", raise_exception=True)
@require_GET
def browse(request):
    """The explorer: a tree of the workspace and one directory's contents."""
    path = request.GET.get("path", "").strip("/")

    try:
        entries = workspace.list_dir(path)
    except (UnsafePath, FileNotFoundError, NotADirectoryError):
        messages.error(request, "That is not a folder in the workspace.")
        return redirect("automation:browse")

    crumbs, walked = [], ""
    for part in [p for p in path.split("/") if p]:
        walked = f"{walked}/{part}" if walked else part
        crumbs.append({"name": part, "path": walked})

    return render(
        request,
        "manage/files.html",
        {
            "section": "files",
            "tree": workspace.tree(),
            "entries": entries,
            "path": path,
            "parent": _parent_of(path),
            "crumbs": crumbs,
            "root": workspace.root(),
        },
    )


@login_required
@permission_required("automation.change_playbook", raise_exception=True)
def edit(request):
    """Open a file for editing. YAML is validated before anything is written."""
    path = request.GET.get("path", "").strip("/")

    try:
        current = workspace.read_file(path)
    except UnsafePath:
        messages.error(request, "That is not a path inside the workspace.")
        return redirect("automation:browse")
    except NotEditable as error:
        messages.error(request, str(error))
        return redirect(_back_to(_parent_of(path)))
    except (FileNotFoundError, IsADirectoryError):
        messages.error(request, f"No file at {path}.")
        return redirect("automation:browse")

    if request.method == "POST":
        form = FileForm(request.POST, path=path)
        if form.is_valid():
            content = form.cleaned_data["content"]
            workspace.write_file(path, content)
            _audit(request, AuditAction.UPDATE, path, detail={"bytes": len(content)})
            messages.success(request, f"{path} saved.")
            return redirect(_url_for("automation:edit", path))
    else:
        form = FileForm(initial={"content": current}, path=path)

    return render(
        request,
        "manage/file_edit.html",
        {
            "section": "files",
            "form": form,
            "path": path,
            "parent": _parent_of(path),
            "is_yaml": path.endswith((".yml", ".yaml")),
        },
    )


@login_required
@permission_required("automation.add_playbook", raise_exception=True)
def create_file(request):
    """Create a file, inside the folder currently being browsed."""
    parent = request.GET.get("path", "").strip("/")

    if request.method == "POST":
        form = FileForm(request.POST, parent=parent, naming=True)
        if form.is_valid():
            path = form.cleaned_data["name"]
            workspace.write_file(path, form.cleaned_data["content"])
            _audit(request, AuditAction.CREATE, path)
            messages.success(request, f"{path} created.")
            return redirect(_url_for("automation:edit", path))
    else:
        form = FileForm(parent=parent, naming=True)

    return render(
        request,
        "manage/file_new.html",
        {"section": "files", "form": form, "parent": parent, "what": "file"},
    )


@login_required
@permission_required("automation.add_playbook", raise_exception=True)
def create_folder(request):
    parent = request.GET.get("path", "").strip("/")

    if request.method == "POST":
        form = NewFolderForm(request.POST, parent=parent)
        if form.is_valid():
            path = form.cleaned_data["name"]
            workspace.create_dir(path)
            _audit(request, AuditAction.CREATE, path, detail={"kind": "folder"})
            messages.success(request, f"{path} created.")
            return redirect(_back_to(path))
    else:
        form = NewFolderForm(parent=parent)

    return render(
        request,
        "manage/file_new.html",
        {"section": "files", "form": form, "parent": parent, "what": "folder"},
    )


@login_required
@permission_required("automation.change_playbook", raise_exception=True)
def rename(request):
    path = request.GET.get("path", "").strip("/")

    try:
        workspace.resolve(path)
    except UnsafePath:
        messages.error(request, "That is not a path inside the workspace.")
        return redirect("automation:browse")

    if request.method == "POST":
        form = RenameForm(request.POST, path=path)
        if form.is_valid():
            target = form.cleaned_data["name"]
            try:
                workspace.rename(path, target)
            except FileExistsError:
                form.add_error("name", "Something already exists at that path.")
            else:
                _audit(
                    request,
                    AuditAction.UPDATE,
                    target,
                    previous={"path": path},
                    detail={"renamed_from": path},
                )
                messages.success(request, f"{path} renamed to {target}.")
                return redirect(_back_to(_parent_of(target)))
    else:
        form = RenameForm(path=path, initial={"name": path})

    return render(
        request,
        "manage/file_rename.html",
        {"section": "files", "form": form, "path": path},
    )


@login_required
@permission_required("automation.delete_playbook", raise_exception=True)
def delete(request):
    """Delete a file or a folder, after saying how much would go."""
    path = request.GET.get("path", "").strip("/")

    try:
        target = workspace.resolve(path)
    except UnsafePath:
        messages.error(request, "That is not a path inside the workspace.")
        return redirect("automation:browse")

    if not target.exists():
        messages.error(request, f"Nothing at {path}.")
        return redirect("automation:browse")

    is_dir = target.is_dir()
    held = workspace.count_files(path)

    if request.method == "POST":
        removed = workspace.delete(path)
        _audit(
            request,
            AuditAction.DELETE,
            path,
            previous={"path": path, "files": removed, "kind": "folder" if is_dir else "file"},
            detail={"files_removed": removed},
        )
        messages.success(
            request,
            f"{path} deleted ({removed} file{'s' if removed != 1 else ''})."
            if is_dir
            else f"{path} deleted.",
        )
        return redirect(_back_to(_parent_of(path)))

    return render(
        request,
        "manage/confirm_delete.html",
        {
            "what": "folder" if is_dir else "file",
            "label": path,
            "blocked_by": (
                f"{held} file{'s' if held != 1 else ''} inside it will be deleted too."
                if is_dir and held
                else "The file is removed from the workspace on disk."
            ),
            "cancel_url": _back_to(_parent_of(path)),
        },
    )

"""The Ansible workspace: ordinary files on disk.

Playbooks are files, not database rows. That is the whole point — everything
written through the web editor stays runnable with plain ``ansible-playbook``,
and the workspace can be handed to Git without an export step.

The one thing this module is strict about is *where* it will write. Every path
a request supplies is resolved and checked against the workspace root, so a
name like ``../../etc/cron.d/x`` is refused rather than followed.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from django.conf import settings

#: The directories a standard Ansible workspace has.
LAYOUT = ("inventories", "playbooks", "roles", "group_vars", "host_vars", "collections")

PLAYBOOK_DIR = "playbooks"
PLAYBOOK_SUFFIXES = (".yml", ".yaml")

#: Deliberately narrow. A path here is a file name, not a shell expression.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

#: What the editor will open as text. Anything else is listed but not edited:
#: rendering a binary in a textarea corrupts it on save.
EDITABLE_SUFFIXES = {".yml", ".yaml", ".cfg", ".ini", ".j2", ".json", ".txt", ".md", ".sh", ".py"}

#: A file larger than this is almost certainly not something to edit in a
#: browser, and holding it in a form field helps nobody.
MAX_EDITABLE_BYTES = 512_000

DEFAULT_ANSIBLE_CFG = """\
# Managed by the Ansible DevOps Platform, and safe to edit by hand.
[defaults]
inventory = inventories
roles_path = roles
host_key_checking = True
stdout_callback = yaml
retry_files_enabled = False

[ssh_connection]
pipelining = True
"""

STARTER_PLAYBOOK = """\
---
- name: {title}
  hosts: all
  gather_facts: true
  become: false

  tasks:
    - name: Ping every host
      ansible.builtin.ping:
"""


class UnsafePath(ValueError):
    """Raised when a supplied name would escape the workspace."""


class NotAPlaybook(ValueError):
    """Raised when a file exists but is not a playbook the editor handles."""


class NotEditable(ValueError):
    """Raised when a file exists but the editor should not open it."""


@dataclass(frozen=True)
class Entry:
    """One file or directory in the workspace, described for listing."""

    path: str
    name: str
    is_dir: bool
    size: int = 0
    modified: datetime | None = None

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix

    @property
    def editable(self) -> bool:
        return (
            not self.is_dir and self.suffix in EDITABLE_SUFFIXES and self.size <= MAX_EDITABLE_BYTES
        )

    @property
    def is_playbook(self) -> bool:
        return (
            not self.is_dir
            and self.suffix in PLAYBOOK_SUFFIXES
            and self.path.startswith(PLAYBOOK_DIR + "/")
        )


@dataclass(frozen=True)
class PlaybookFile:
    """A playbook on disk, described for listing."""

    name: str
    size: int
    modified: datetime

    @property
    def path(self) -> Path:
        return playbook_path(self.name)


def root() -> Path:
    return Path(settings.ANSIBLE_WORKSPACE)


def ensure_layout() -> Path:
    """Create the standard workspace directories, and an ansible.cfg once.

    Idempotent, so it is safe to call on every request that needs the
    workspace rather than making the operator run a setup step.
    """
    base = root()
    for directory in LAYOUT:
        (base / directory).mkdir(parents=True, exist_ok=True)

    config = base / "ansible.cfg"
    if not config.exists():
        config.write_text(DEFAULT_ANSIBLE_CFG, encoding="utf-8")
    return base


def playbook_path(name: str) -> Path:
    """Resolve *name* to a path inside ``playbooks/``, or refuse it."""
    name = (name or "").strip()
    # An absolute path is refused rather than reinterpreted: silently turning
    # /etc/cron.d/x.yml into a workspace file writes somewhere nobody asked for.
    if not name or not _SAFE_NAME.match(name) or ".." in name.split("/"):
        raise UnsafePath(f"{name!r} is not a valid playbook name.")
    if not name.endswith(PLAYBOOK_SUFFIXES):
        raise NotAPlaybook("A playbook must be a .yml or .yaml file.")

    base = os.path.realpath(root() / PLAYBOOK_DIR)
    candidate = os.path.realpath(os.path.join(base, name))
    # realpath collapses symlinks and traversal; the prefix check is the whole
    # guarantee, written so it is obvious that nothing outside can be reached.
    if not candidate.startswith(base + os.sep):
        raise UnsafePath(f"{name!r} is outside the workspace.")
    return Path(candidate)


def list_playbooks() -> list[PlaybookFile]:
    """Every playbook in the workspace, nested directories included."""
    base = ensure_layout() / PLAYBOOK_DIR
    found = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix in PLAYBOOK_SUFFIXES:
            stat = path.stat()
            found.append(
                PlaybookFile(
                    name=str(path.relative_to(base)),
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
    return found


def read_playbook(name: str) -> str:
    path = playbook_path(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    return path.read_text(encoding="utf-8")


def write_playbook(name: str, content: str) -> Path:
    """Write *content*, creating any parent directory the name implies."""
    path = playbook_path(name)
    ensure_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Normalise what a browser textarea produces: CRLF is valid YAML but a
    # nuisance in every diff afterwards, and a file with no final newline makes
    # the next diff claim a line changed that did not.
    text = content.replace("\r\n", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def delete_playbook(name: str) -> None:
    path = playbook_path(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    path.unlink()


def validate_syntax(content: str) -> list[str]:
    """Check that *content* is YAML at all.

    This is what any YAML file in the workspace owes: group_vars is a mapping,
    a playbook is a list of plays, and an inventory is neither. Structure is
    checked by whoever knows what the file is for.
    """
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as error:
        return [f"Invalid YAML: {_yaml_message(error)}"]
    return []


def validate(content: str) -> list[str]:
    """Check *content* the way Ansible would, and say what is wrong.

    Returns a list of human-readable problems — empty means it looks like a
    playbook. This is a structural check, not a substitute for ansible-lint:
    it catches the mistakes that stop a file loading at all, which is what an
    editor owes you before you hit run.
    """
    try:
        document = yaml.safe_load(content)
    except yaml.YAMLError as error:
        return [f"Invalid YAML: {_yaml_message(error)}"]

    if document is None:
        return ["The file is empty."]
    if not isinstance(document, list):
        return ["A playbook is a list of plays, so the file must start with '- name:'."]

    problems = []
    for index, play in enumerate(document, start=1):
        where = f"Play {index}"
        if not isinstance(play, dict):
            problems.append(f"{where} is not a mapping.")
            continue
        if "hosts" not in play and "import_playbook" not in play:
            problems.append(f"{where} has no 'hosts'.")
        has_work = any(key in play for key in ("tasks", "roles", "import_playbook"))
        if not has_work:
            problems.append(f"{where} has no 'tasks' or 'roles', so it would do nothing.")
    return problems


def _yaml_message(error: yaml.YAMLError) -> str:
    """PyYAML's own message, with the line number the editor can act on."""
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", None) or str(error)
    return f"line {mark.line + 1}, column {mark.column + 1}: {problem}" if mark else problem


# --- the workspace as a file tree -------------------------------------------
#
# Everything below treats the workspace the way an editor does: paths, folders
# and files, rather than playbooks specifically. The playbook helpers above are
# the same operations with a narrower door.


def resolve(relative: str, *, allow_root: bool = False) -> Path:
    """Resolve a workspace-relative path, or refuse it.

    The single place that decides whether a path a request supplied is inside
    the workspace. Everything that touches disk goes through here.
    """
    relative = (relative or "").strip()
    base = ensure_layout().resolve()

    # Refuse an absolute path rather than reinterpreting it: quietly turning
    # /etc/passwd into a workspace file writes somewhere nobody asked for.
    if relative.startswith("/"):
        raise UnsafePath(f"{relative!r} is an absolute path.")
    relative = relative.strip("/")

    root = os.path.realpath(base)

    if not relative:
        if allow_root:
            return Path(root)
        raise UnsafePath("A path is required.")

    if not _SAFE_NAME.match(relative) or ".." in relative.split("/"):
        raise UnsafePath(f"{relative!r} is not a valid path.")

    # realpath collapses symlinks and traversal; this single prefix check is
    # then the whole guarantee. Requiring the separator also rejects the root
    # itself and a sibling directory whose name merely starts the same way.
    candidate = os.path.realpath(os.path.join(root, relative))
    if not candidate.startswith(root + os.sep):
        raise UnsafePath(f"{relative!r} is outside the workspace.")
    return Path(candidate)


def relative_to_root(path: Path) -> str:
    return str(path.relative_to(ensure_layout().resolve()))


def _entry_for(path: Path) -> Entry:
    stat = path.stat()
    return Entry(
        path=relative_to_root(path),
        name=path.name,
        is_dir=path.is_dir(),
        size=0 if path.is_dir() else stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def list_dir(relative: str = "") -> list[Entry]:
    """One directory's contents, folders first, as an editor would show them."""
    directory = resolve(relative, allow_root=True)
    if not directory.is_dir():
        raise NotADirectoryError(relative)

    entries = [_entry_for(child) for child in directory.iterdir() if not child.name.startswith(".")]
    return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))


def tree(relative: str = "", *, depth: int = 6) -> list[dict]:
    """The workspace as a nested structure, for an explorer sidebar."""
    if depth <= 0:
        return []

    nodes = []
    for entry in list_dir(relative):
        node = {"entry": entry, "children": []}
        if entry.is_dir:
            node["children"] = tree(entry.path, depth=depth - 1)
        nodes.append(node)
    return nodes


def read_file(relative: str) -> str:
    """Read a text file the editor is allowed to open."""
    path = resolve(relative)
    if not path.is_file():
        raise FileNotFoundError(relative)
    if path.suffix not in EDITABLE_SUFFIXES:
        raise NotEditable(f"{path.name} is not a file this editor opens.")
    if path.stat().st_size > MAX_EDITABLE_BYTES:
        raise NotEditable(f"{path.name} is too large to edit in a browser.")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise NotEditable(f"{path.name} is not text.") from None


def write_file(relative: str, content: str) -> Path:
    """Write a text file, creating any directory the path implies."""
    path = resolve(relative)
    if path.exists() and path.is_dir():
        raise UnsafePath(f"{relative!r} is a directory.")
    if path.suffix not in EDITABLE_SUFFIXES:
        raise NotEditable(f"{path.name} is not a file this editor writes.")

    path.parent.mkdir(parents=True, exist_ok=True)
    text = content.replace("\r\n", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def create_dir(relative: str) -> Path:
    path = resolve(relative)
    if path.exists():
        raise FileExistsError(relative)
    path.mkdir(parents=True)
    return path


def delete(relative: str) -> int:
    """Delete a file, or a directory and everything under it.

    Returns how many files went, so the audit trail can say more than "a
    folder was removed" — deleting roles/nginx is not a small thing.
    """
    path = resolve(relative)
    if not path.exists():
        raise FileNotFoundError(relative)

    if path.is_dir():
        removed = sum(1 for child in path.rglob("*") if child.is_file())
        shutil.rmtree(path)
        return removed

    path.unlink()
    return 1


def rename(relative: str, new_relative: str) -> Path:
    """Move a file or directory within the workspace."""
    source = resolve(relative)
    target = resolve(new_relative)
    if not source.exists():
        raise FileNotFoundError(relative)
    if target.exists():
        raise FileExistsError(new_relative)

    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def count_files(relative: str) -> int:
    """How many files a path holds, for a confirmation that means something."""
    path = resolve(relative)
    if path.is_file():
        return 1
    return sum(1 for child in path.rglob("*") if child.is_file())

"""The Ansible workspace: ordinary files on disk.

Playbooks are files, not database rows. That is the whole point — everything
written through the web editor stays runnable with plain ``ansible-playbook``,
and the workspace can be handed to Git without an export step.

The one thing this module is strict about is *where* it will write. Every path
a request supplies is resolved and checked against the workspace root, so a
name like ``../../etc/cron.d/x`` is refused rather than followed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from django.conf import settings

#: The directories a standard Ansible workspace has.
LAYOUT = ("inventories", "playbooks", "roles", "group_vars", "host_vars", "collections")

PLAYBOOK_DIR = "playbooks"
PLAYBOOK_SUFFIXES = (".yml", ".yaml")

#: Deliberately narrow. A playbook name is a file name, not a shell expression.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

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

    base = (root() / PLAYBOOK_DIR).resolve()
    candidate = (base / name).resolve()
    # resolve() collapses symlinks and traversal, so this is the real check.
    if not candidate.is_relative_to(base):
        raise UnsafePath(f"{name!r} is outside the workspace.")
    return candidate


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

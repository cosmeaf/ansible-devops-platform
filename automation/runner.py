"""Run Ansible, for real.

Everything the platform executes goes through here, so there is one place that
knows how a credential becomes a connection and how a result becomes something
the database can store.

ansible-runner is used rather than shelling out to ansible-playbook: it gives
structured events and a return code instead of output that has to be parsed,
and it is the interface Ansible itself supports for this.

Secrets live on disk only for the duration of a run, inside a private data
directory created with 0700 and removed in a finally block. Ansible has to
read a key or a password from somewhere; the guarantee made here is that it is
never a shared location and never outlives the run.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import ansible_runner
import yaml

from credentials.models import CredentialType
from inventory.builder import to_yaml

from .known_hosts import known_hosts_path

#: Ansible's own vocabulary for how a run ended.
SUCCESSFUL = "successful"
FAILED = "failed"
TIMEOUT = "timeout"
CANCELED = "canceled"


@dataclass
class HostResult:
    """One host's line of the play recap."""

    host: str
    ok: int = 0
    changed: int = 0
    failures: int = 0
    unreachable: int = 0
    skipped: int = 0

    @property
    def reached(self) -> bool:
        return self.unreachable == 0


@dataclass
class RunResult:
    """What a run produced, reduced to what the platform stores."""

    status: str
    rc: int
    stdout: str = ""
    hosts: dict[str, HostResult] = field(default_factory=dict)

    @property
    def successful(self) -> bool:
        return self.status == SUCCESSFUL and self.rc == 0

    @property
    def any_unreachable(self) -> bool:
        return any(not host.reached for host in self.hosts.values())

    def summary(self) -> str:
        """A single line fit for a status column or an audit entry."""
        if not self.hosts:
            return self.status
        totals = {
            "ok": sum(h.ok for h in self.hosts.values()),
            "changed": sum(h.changed for h in self.hosts.values()),
            "failed": sum(h.failures for h in self.hosts.values()),
            "unreachable": sum(h.unreachable for h in self.hosts.values()),
        }
        return " ".join(f"{key}={value}" for key, value in totals.items())


def run_module(
    servers,
    *,
    module: str,
    module_args: str = "",
    credential=None,
    timeout: int = 30,
) -> RunResult:
    """Run a single module — the shape a connection test takes."""
    return _execute(
        servers,
        credential=credential,
        timeout=timeout,
        module=module,
        module_args=module_args,
        host_pattern="all",
    )


def run_playbook(
    servers,
    *,
    playbook: str,
    credential=None,
    limit: str = "",
    tags: str = "",
    extra_vars: dict | None = None,
    check_mode: bool = False,
    timeout: int = 1800,
) -> RunResult:
    """Run a playbook from the workspace against *servers*."""
    from .workspace import playbook_path

    return _execute(
        servers,
        credential=credential,
        timeout=timeout,
        playbook=str(playbook_path(playbook)),
        limit=limit,
        tags=tags,
        extra_vars=extra_vars or {},
        check_mode=check_mode,
    )


def _execute(
    servers,
    *,
    credential,
    timeout: int,
    module: str = "",
    module_args: str = "",
    host_pattern: str = "",
    playbook: str = "",
    limit: str = "",
    tags: str = "",
    extra_vars: dict | None = None,
    check_mode: bool = False,
) -> RunResult:
    """Build a private data directory, run, and clean up whatever it held."""
    private_dir = Path(tempfile.mkdtemp(prefix="ansible-run-"))
    os.chmod(private_dir, stat.S_IRWXU)  # 0700: nothing here is anyone else's

    try:
        inventory = _inventory_for(servers, credential=credential, directory=private_dir)
        (private_dir / "inventory").mkdir(exist_ok=True)
        (private_dir / "inventory" / "hosts.yml").write_text(inventory, encoding="utf-8")

        settings = {
            "job_timeout": timeout,
            # Host key checking is a real protection, but it cannot be answered
            # interactively from a worker. Left on; an unknown host fails the
            # run rather than trusting whatever answered.
            "suppress_ansible_output": True,
        }

        arguments = {
            "private_data_dir": str(private_dir),
            "settings": settings,
            "quiet": True,
            "envvars": {
                "ANSIBLE_HOST_KEY_CHECKING": "True",
                "ANSIBLE_RETRY_FILES_ENABLED": "False",
                # BatchMode is not an optimisation. Without it ssh asks whether
                # to accept an unknown host key and waits for an answer that a
                # worker can never give, turning a refusal into a timeout.
                # UserKnownHostsFile points at the keys a person has accepted;
                # a host that is not in there fails immediately and says so.
                "ANSIBLE_SSH_ARGS": (
                    "-o BatchMode=yes "
                    "-o StrictHostKeyChecking=yes "
                    f"-o UserKnownHostsFile={known_hosts_path()} "
                    "-o ControlMaster=auto -o ControlPersist=60s"
                ),
                # runner executes the ansible binaries by name. They live
                # beside the interpreter running us, which is not on PATH when
                # a worker was started from a virtualenv by absolute path.
                "PATH": _executable_path(),
            },
        }
        if playbook:
            arguments["playbook"] = playbook
            if limit:
                arguments["limit"] = limit
            if tags:
                arguments["tags"] = tags
            if extra_vars:
                arguments["extravars"] = dict(extra_vars)
            if check_mode:
                arguments["cmdline"] = "--check"
        else:
            arguments["module"] = module
            arguments["host_pattern"] = host_pattern or "all"
            if module_args:
                arguments["module_args"] = module_args

        run = ansible_runner.run(**arguments)
        return _result_from(run)
    finally:
        # The key material and any password written above lived only here.
        shutil.rmtree(private_dir, ignore_errors=True)


def _executable_path() -> str:
    """PATH with this interpreter's script directory in front."""
    scripts = str(Path(sys.executable).parent)
    current = os.environ.get("PATH", "")
    return f"{scripts}{os.pathsep}{current}" if current else scripts


def _inventory_for(servers, *, credential, directory: Path) -> str:
    """Render an inventory for *servers*, wired to *credential*.

    The connection variables Ansible needs are added to the generated
    inventory rather than passed on a command line, where they would show up
    in a process listing.
    """
    hosts = {}
    for server in servers:
        entry = server.to_inventory_host()
        server_credential = credential or getattr(server, "credential", None)
        if server_credential is not None:
            entry.update(_connection_vars(server_credential, directory=directory))
        hosts[server.name] = entry

    return to_yaml({"all": {"hosts": hosts}})


def _connection_vars(credential, *, directory: Path) -> dict:
    """Turn a stored credential into Ansible connection variables."""
    secret = credential.reveal_secret()
    variables: dict[str, str] = {}

    if credential.username:
        variables["ansible_user"] = credential.username

    if credential.type == CredentialType.SSH_PRIVATE_KEY:
        key_file = directory / "id_key"
        key_file.write_text(secret if secret.endswith("\n") else secret + "\n", encoding="utf-8")
        os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600, or ssh refuses it
        variables["ansible_ssh_private_key_file"] = str(key_file)
    elif credential.type == CredentialType.SSH_PASSWORD:
        variables["ansible_password"] = secret
    elif credential.type == CredentialType.BECOME_PASSWORD:
        variables["ansible_become_password"] = secret

    return variables


def _result_from(run) -> RunResult:
    """Reduce an ansible-runner result to what the platform stores."""
    hosts = {}
    for host, stats in _recap(run).items():
        hosts[host] = stats

    return RunResult(
        status=run.status or FAILED,
        rc=run.rc if run.rc is not None else 1,
        stdout=_stdout(run),
        hosts=hosts,
    )


def _recap(run) -> dict[str, HostResult]:
    """Read the play recap out of runner's stats."""
    stats = getattr(run, "stats", None) or {}
    names = set()
    for bucket in ("ok", "changed", "failures", "dark", "skipped"):
        names.update((stats.get(bucket) or {}).keys())

    recap = {}
    for name in sorted(names):
        recap[name] = HostResult(
            host=name,
            ok=(stats.get("ok") or {}).get(name, 0),
            changed=(stats.get("changed") or {}).get(name, 0),
            failures=(stats.get("failures") or {}).get(name, 0),
            # runner calls unreachable hosts "dark", which no operator does.
            unreachable=(stats.get("dark") or {}).get(name, 0),
            skipped=(stats.get("skipped") or {}).get(name, 0),
        )
    return recap


def _stdout(run) -> str:
    try:
        return run.stdout.read() if run.stdout else ""
    except (OSError, ValueError):
        return ""


def parse_extra_vars(text: str) -> dict:
    """Parse the extra vars an operator typed, as YAML.

    YAML because that is what Ansible itself accepts and what someone writing
    ``app_version: 4.12.0`` expects. A mapping is required: a bare list or
    scalar is not something --extra-vars can use.
    """
    text = (text or "").strip()
    if not text:
        return {}

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(f"Extra vars are not valid YAML: {error}") from None

    if not isinstance(parsed, dict):
        raise ValueError("Extra vars must be a mapping, such as 'app_version: 4.12.0'.")
    return parsed

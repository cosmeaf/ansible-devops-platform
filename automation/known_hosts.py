"""Deciding which host keys the platform trusts.

Host key checking is the only thing standing between a run and a machine
pretending to be the one you meant, so it stays on. But a worker cannot answer
"are you sure you want to continue connecting?", and leaving it to answer yes
automatically would remove the protection entirely.

So trust is explicit and it is recorded: the fingerprint is fetched, shown to
a person, and only written to the known_hosts file when they accept it. Trust
on first use, with a human in the loop, rather than trust in the dark.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

#: Lives in the workspace so it survives a rebuild and is shared by every
#: worker, exactly like the playbooks are.
KNOWN_HOSTS_NAME = "known_hosts"

SCAN_TIMEOUT = 10


class ScanFailed(RuntimeError):
    """The host did not offer a key we could read."""


@dataclass(frozen=True)
class HostKey:
    """One key a host offered, with the fingerprint a person can compare."""

    host: str
    port: int
    key_type: str
    fingerprint: str
    line: str

    @property
    def label(self) -> str:
        return f"{self.key_type} {self.fingerprint}"


def _tool(name: str) -> str:
    """Resolve an OpenSSH tool to its full path.

    Being explicit about which binary runs is worth the lookup; falling back
    to the bare name only matters if PATH is all we have.
    """
    return shutil.which(name) or name


def known_hosts_path() -> Path:
    path = Path(settings.ANSIBLE_WORKSPACE) / KNOWN_HOSTS_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return path


def scan(host: str, port: int = 22) -> list[HostKey]:
    """Ask the host which keys it offers, without trusting any of them yet."""
    try:
        # A fixed argument list, never a shell: `host` comes from a database
        # field and is passed as one argument, so it cannot become a command.
        scanned = subprocess.run(  # noqa: S603 - fixed argv, shell=False
            [_tool("ssh-keyscan"), "-p", str(port), "-T", str(SCAN_TIMEOUT), host],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT + 5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ScanFailed(f"Could not reach {host} on port {port}: {error}") from None

    lines = [line for line in scanned.stdout.splitlines() if line and not line.startswith("#")]
    if not lines:
        raise ScanFailed(
            f"{host} offered no host key on port {port}. It may be unreachable, "
            "or something other than SSH may be listening."
        )

    return [key for line in lines if (key := _fingerprint_of(line, host, port))]


def _fingerprint_of(line: str, host: str, port: int) -> HostKey | None:
    """Turn a known_hosts line into the fingerprint ssh would show."""
    described = subprocess.run(  # noqa: S603 - fixed argv, shell=False
        [_tool("ssh-keygen"), "-l", "-f", "-"],
        input=line,
        capture_output=True,
        text=True,
        check=False,
    )
    if described.returncode != 0 or not described.stdout.strip():
        return None

    # "256 SHA256:abc... host (ED25519)"
    parts = described.stdout.split()
    fingerprint = parts[1] if len(parts) > 1 else ""
    key_type = parts[-1].strip("()") if parts else ""
    return HostKey(host=host, port=port, key_type=key_type, fingerprint=fingerprint, line=line)


def is_trusted(host: str, port: int = 22) -> bool:
    """Whether a key for *host* has already been accepted."""
    entries = known_hosts_path().read_text(encoding="utf-8").splitlines()
    needle = host if port == 22 else f"[{host}]:{port}"
    return any(line.split()[0].split(",")[0] == needle for line in entries if line.strip())


def trust(keys: list[HostKey]) -> int:
    """Record *keys* as accepted. Returns how many lines were added."""
    path = known_hosts_path()
    existing = set(path.read_text(encoding="utf-8").splitlines())

    added = [key.line for key in keys if key.line not in existing]
    if added:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(added) + "\n")
    return len(added)


def forget(host: str, port: int = 22) -> int:
    """Remove every accepted key for *host*, so it must be trusted again."""
    path = known_hosts_path()
    needle = host if port == 22 else f"[{host}]:{port}"

    kept, removed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and line.split()[0].split(",")[0] == needle:
            removed += 1
            continue
        kept.append(line)

    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed

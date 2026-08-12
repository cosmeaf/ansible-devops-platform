"""Parse an OpenSSH client config into inventory candidates.

Most people already describe their fleet in ``~/.ssh/config``. Re-typing it into
a web form is exactly the kind of busywork a platform should absorb, so this
reads that file and produces registrable hosts.

Only the directives that map onto Ansible connection variables are read;
everything else is ignored rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: A comment made only of rule characters — the top or bottom of a banner.
_RULE = re.compile(r"^#[#=\-*_\s]*$")

#: Directives we understand. Anything else in the file is skipped.
_INTERESTING = {
    "hostname": "hostname",
    "user": "user",
    "port": "port",
    "identityfile": "identity_file",
    "proxyjump": "proxy_jump",
    "proxycommand": "proxy_command",
}


@dataclass
class SSHHost:
    """One ``Host`` block, reduced to what the platform needs."""

    aliases: list[str]
    hostname: str = ""
    user: str = ""
    port: int | None = None
    identity_file: str = ""
    proxy_jump: str = ""
    proxy_command: str = ""
    #: The banner comment this block sits under, if the file uses them.
    section: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        """The first alias, which is what a person actually types."""
        return self.aliases[0]

    @property
    def client_name(self) -> str:
        """The section title as a client name.

        Banners are shouted by convention; a client list reads better without
        the shouting, and ``S2DIGITAL`` still comes out as ``S2Digital``.
        """
        return self.section.title() if self.section.isupper() else self.section

    @property
    def is_wildcard(self) -> bool:
        return any("*" in alias or "?" in alias for alias in self.aliases)

    @property
    def reaches_a_host(self) -> bool:
        return bool(self.hostname or self.name)

    @property
    def needs_a_jump(self) -> bool:
        """True when the host is only reachable through another one."""
        return bool(self.proxy_jump or self.proxy_command)


def _banner_title(lines: list[str], index: int) -> str:
    """Return the section title if the comment at *index* is a banner.

    People group an ssh_config with banners, and the title is almost always the
    client or project the hosts below belong to — worth keeping. Two shapes are
    recognised: a title sandwiched between rule lines, and a title written on
    the rule itself (``#### VELOMA``). An ordinary comment explaining a
    directive is neither, and is ignored.
    """
    line = lines[index]
    if _RULE.match(line):
        return ""

    title = line.lstrip("#").strip(" -=*_")
    if not title:
        return ""

    # `#### VELOMA` — the rule and the title on one line.
    if line[:4].count("#") + line[:4].count("=") + line[:4].count("-") >= 3:
        return title

    def neighbour(step: int) -> str:
        cursor = index + step
        while 0 <= cursor < len(lines) and not lines[cursor]:
            cursor += step
        return lines[cursor] if 0 <= cursor < len(lines) else ""

    if _RULE.match(neighbour(-1)) and _RULE.match(neighbour(1)):
        return title
    return ""


def parse(text: str) -> list[SSHHost]:
    """Parse *text* as an ssh_config, returning one entry per ``Host`` block."""
    hosts: list[SSHHost] = []
    current: SSHHost | None = None
    section = ""

    lines = [raw.strip() for raw in text.splitlines()]
    for index, line in enumerate(lines):
        if not line:
            continue

        if line.startswith("#"):
            if title := _banner_title(lines, index):
                section = title
            continue

        # Directives may be separated by whitespace or '='.
        parts = re.split(r"[\s=]+", line, maxsplit=1)
        if len(parts) != 2:
            continue
        keyword, value = parts[0].lower(), parts[1].strip()

        if keyword == "host":
            current = SSHHost(aliases=value.split(), section=section)
            hosts.append(current)
            continue

        if current is None:
            continue  # a directive before any Host block applies globally

        if attribute := _INTERESTING.get(keyword):
            if attribute == "port":
                try:
                    current.port = int(value)
                except ValueError:
                    continue
            else:
                setattr(current, attribute, value)

    return hosts


def parse_file(path: str | Path) -> list[SSHHost]:
    return parse(Path(path).expanduser().read_text(encoding="utf-8"))


def importable(hosts: list[SSHHost], *, skip_patterns: tuple[str, ...] = ()) -> list[SSHHost]:
    """Filter to hosts worth registering as managed servers.

    Drops wildcard blocks, entries with no address, and anything matching
    *skip_patterns* — Git forge entries in particular are SSH endpoints but not
    machines anyone manages with Ansible.
    """
    keep = []
    for host in hosts:
        if host.is_wildcard or not host.reaches_a_host:
            continue
        haystack = " ".join(host.aliases + [host.hostname]).lower()
        if any(pattern.lower() in haystack for pattern in skip_patterns):
            continue
        keep.append(host)
    return keep

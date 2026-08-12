"""Render the registered fleet as a standard Ansible YAML inventory.

The output is what the ``ansible.builtin.yaml`` inventory plugin expects, so it
works with plain ``ansible-playbook -i hosts.yml`` and with
``ansible-inventory --graph``. Nothing here is proprietary: if the platform
disappears, the file it produced keeps working.

Host variables are written once under ``all.hosts``; the groups below only
record membership. That keeps a fleet of a few hundred hosts readable, and
means an address is never stated twice and cannot disagree with itself.
"""

from __future__ import annotations

import re

import yaml

from infrastructure.models import Server

#: Ansible group names may only hold letters, digits and underscores. Anything
#: else is replaced rather than rejected — a group called "web servers" is a
#: reasonable thing for a person to write.
_INVALID_IN_GROUP_NAME = re.compile(r"[^A-Za-z0-9_]")

#: Environments and clients share a namespace with user-defined groups, so they
#: are prefixed. `production` as a group name stays available for whoever wants
#: it, and `env_production` always means the environment.
ENVIRONMENT_PREFIX = "env_"
CLIENT_PREFIX = "client_"


def ansible_group_name(value: str) -> str:
    """Return *value* as a name Ansible will accept for a group."""
    name = _INVALID_IN_GROUP_NAME.sub("_", value.strip()).strip("_")
    # A group cannot start with a digit; Ansible parses that as a range.
    return f"g_{name}" if not name or name[0].isdigit() else name


def servers_for(*, environment=None, client=None, include_inactive: bool = False):
    """The servers an inventory should contain, in inventory order."""
    queryset = Server.objects.select_related("environment", "client").prefetch_related("groups")
    if not include_inactive:
        queryset = queryset.filter(active=True)
    if environment is not None:
        queryset = queryset.filter(environment__slug=_slug(environment))
    if client is not None:
        queryset = queryset.filter(client__slug=_slug(client))
    return queryset.order_by("name")


def build(*, environment=None, client=None, include_inactive: bool = False) -> dict:
    """Build the inventory as a plain dict, ready to serialise."""
    hosts: dict[str, dict] = {}
    children: dict[str, dict] = {}

    def join(group: str, host: str) -> None:
        children.setdefault(group, {"hosts": {}})["hosts"][host] = None

    for server in servers_for(
        environment=environment, client=client, include_inactive=include_inactive
    ):
        hosts[server.name] = server.to_inventory_host()

        for group in server.groups.all():
            join(ansible_group_name(group.slug or group.name), server.name)
        if server.environment_id:
            join(ENVIRONMENT_PREFIX + ansible_group_name(server.environment.slug), server.name)
        if server.client_id:
            join(CLIENT_PREFIX + ansible_group_name(server.client.slug), server.name)

    inventory: dict = {"all": {"hosts": hosts}}
    if children:
        inventory["all"]["children"] = dict(sorted(children.items()))
    return inventory


def to_yaml(inventory: dict) -> str:
    """Serialise *inventory* the way a person would have written it by hand."""
    return yaml.safe_dump(inventory, sort_keys=False, default_flow_style=False, width=100)


def render(*, environment=None, client=None, include_inactive: bool = False) -> str:
    return to_yaml(build(environment=environment, client=client, include_inactive=include_inactive))


def graph(inventory: dict) -> str:
    """Render the inventory the way ``ansible-inventory --graph`` does.

    Useful on a web page for the same reason it is useful in a terminal: it
    answers "what would --limit actually hit?" at a glance.
    """
    root = inventory.get("all", {})
    children = root.get("children") or {}
    lines = ["@all:"]

    grouped = {host for body in children.values() for host in (body.get("hosts") or {})}
    if ungrouped := [h for h in (root.get("hosts") or {}) if h not in grouped]:
        lines.append("  |--@ungrouped:")
        lines.extend(f"  |  |--{host}" for host in ungrouped)

    for group, body in children.items():
        lines.append(f"  |--@{group}:")
        lines.extend(f"  |  |--{host}" for host in (body.get("hosts") or {}))
    return "\n".join(lines)


def _slug(value) -> str:
    """Accept a model instance or a slug, so callers can pass either."""
    return getattr(value, "slug", value)

"""Register servers from an existing OpenSSH client config.

Idempotent: a host already registered under the same name is reported and left
alone, never silently overwritten.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from infrastructure.models import Client, Environment, Server, ServerGroup
from infrastructure.ssh_config import importable, parse_file

#: Git forges answer SSH but are not machines anyone manages with Ansible.
DEFAULT_SKIP = ("github.com", "gitlab.com", "bitbucket.org", "git@")


class Command(BaseCommand):
    help = "Register servers from an ssh_config file (default: ~/.ssh/config)."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="~/.ssh/config")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be registered without writing anything.",
        )
        parser.add_argument("--client", help="Assign every imported server to this client name.")
        parser.add_argument(
            "--environment", help="Assign every imported server to this environment."
        )
        parser.add_argument(
            "--group", action="append", default=[], help="Add to this group. Repeatable."
        )
        parser.add_argument(
            "--skip",
            action="append",
            default=[],
            help="Skip hosts matching this substring. Repeatable.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser()
        if not path.is_file():
            raise CommandError(f"No ssh_config at {path}")

        hosts = importable(parse_file(path), skip_patterns=DEFAULT_SKIP + tuple(options["skip"]))
        if not hosts:
            self.stdout.write("Nothing importable found.")
            return

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — nothing will be written.\n"))

        with transaction.atomic():
            client = environment = None
            groups = []
            if not dry_run:
                if name := options.get("client"):
                    client, _ = Client.objects.get_or_create(name=name)
                if name := options.get("environment"):
                    environment, _ = Environment.objects.get_or_create(name=name)
                groups = [ServerGroup.objects.get_or_create(name=g)[0] for g in options["group"]]

            created = skipped = 0
            for host in hosts:
                exists = Server.objects.filter(name=host.name).exists()
                jump = " via jump host" if host.needs_a_jump else ""
                address = host.hostname or host.name

                if exists:
                    skipped += 1
                    self.stdout.write(f"  = {host.name:<28} {address:<18} already registered")
                    continue

                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  + {host.name:<28} {address:<18} "
                        f"user={host.user or 'ansible':<10}port={host.port or 22}{jump}"
                    )
                )
                if dry_run:
                    continue

                server = Server.objects.create(
                    name=host.name,
                    hostname=host.hostname if not _looks_like_ip(host.hostname) else "",
                    primary_ip=host.hostname if _looks_like_ip(host.hostname) else None,
                    ansible_user=host.user or "ansible",
                    ssh_port=host.port or 22,
                    client=client,
                    environment=environment,
                    description=(
                        f"Imported from {path.name}"
                        + (f"; reachable via {host.proxy_jump}" if host.proxy_jump else "")
                    ),
                )
                if groups:
                    server.groups.set(groups)

            if dry_run:
                transaction.set_rollback(True)

        verb = "would be registered" if dry_run else "registered"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{created} {verb}, {skipped} already present."))
        if any(h.needs_a_jump for h in hosts):
            self.stdout.write(
                self.style.WARNING(
                    "Some hosts are reachable only through a jump host or VPN. "
                    "Their address was imported, but the platform cannot reach them "
                    "until the runner has the same network path."
                )
            )


def _looks_like_ip(value: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

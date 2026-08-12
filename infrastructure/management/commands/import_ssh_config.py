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
        parser.add_argument(
            "--client",
            help="Assign every imported server to this client name, ignoring section banners.",
        )
        parser.add_argument(
            "--no-section-clients",
            dest="section_clients",
            action="store_false",
            help="Do not turn banner comments (# AVALIZA) into clients.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Fill in client, environment and groups on servers already registered "
            "without them. Never overwrites a value that is already set.",
        )
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

        # Everything below runs inside the transaction, so a dry run can create
        # and report the same objects a real run would and then roll them back.
        with transaction.atomic():
            forced_client = options.get("client")
            environment = None
            if name := options.get("environment"):
                environment, _ = Environment.objects.get_or_create(name=name)
            groups = [ServerGroup.objects.get_or_create(name=g)[0] for g in options["group"]]

            created = updated = skipped = 0
            for host in hosts:
                client_name = forced_client or (
                    host.client_name if options["section_clients"] else ""
                )
                jump = " via jump host" if host.needs_a_jump else ""
                address = host.hostname or host.name

                if server := Server.objects.filter(name=host.name).first():
                    changes = (
                        self._backfill(server, client_name, environment, groups)
                        if options["update_existing"]
                        else []
                    )
                    if changes:
                        updated += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ~ {host.name:<28} {address:<18} {', '.join(changes)}"
                            )
                        )
                    else:
                        skipped += 1
                        self.stdout.write(f"  = {host.name:<28} {address:<18} already registered")
                    continue

                created += 1
                owner = f"client={client_name} " if client_name else ""
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  + {host.name:<28} {address:<18} {owner}"
                        f"user={host.user or 'ansible':<10}port={host.port or 22}{jump}"
                    )
                )

                server = Server.objects.create(
                    name=host.name,
                    hostname=host.hostname if not _looks_like_ip(host.hostname) else "",
                    primary_ip=host.hostname if _looks_like_ip(host.hostname) else None,
                    ansible_user=host.user or "ansible",
                    ssh_port=host.port or 22,
                    client=_client_for(client_name),
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
        summary = f"{created} {verb}, {updated} updated, {skipped} already present."
        self.stdout.write(self.style.SUCCESS(summary))
        if any(h.needs_a_jump for h in hosts):
            self.stdout.write(
                self.style.WARNING(
                    "Some hosts are reachable only through a jump host or VPN. "
                    "Their address was imported, but the platform cannot reach them "
                    "until the runner has the same network path."
                )
            )

    def _backfill(self, server, client_name, environment, groups) -> list[str]:
        """Fill in what an already-registered server is missing.

        Only ever fills a blank: a server someone has since assigned by hand
        keeps what they chose.
        """
        changes = []
        if client_name and server.client is None:
            server.client = _client_for(client_name)
            changes.append(f"client={client_name}")
        if environment and server.environment is None:
            server.environment = environment
            changes.append(f"environment={environment}")
        if changes:
            server.save()

        if missing := [g for g in groups if not server.groups.filter(pk=g.pk).exists()]:
            server.groups.add(*missing)
            changes.append("groups+" + ",".join(g.name for g in missing))
        return changes


def _client_for(name: str) -> Client | None:
    return Client.objects.get_or_create(name=name)[0] if name else None


def _looks_like_ip(value: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

"""Write the registered fleet out as a standard Ansible inventory file.

    python manage.py generate_inventory
    python manage.py generate_inventory --environment production -o inventories/production/hosts.yml

The result is an ordinary YAML inventory. Feed it straight to ansible:

    ansible-inventory -i inventories/production/hosts.yml --graph
    ansible-playbook  -i inventories/production/hosts.yml playbooks/update.yml
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from infrastructure.models import Client, Environment
from inventory.builder import build, graph, render


class Command(BaseCommand):
    help = "Generate an Ansible YAML inventory from the registered servers."

    def add_arguments(self, parser):
        parser.add_argument("--environment", help="Limit to this environment (slug or name).")
        parser.add_argument("--client", help="Limit to this client (slug or name).")
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include servers marked inactive. They are left out by default.",
        )
        parser.add_argument("-o", "--output", help="Write to this file instead of standard output.")
        parser.add_argument(
            "--graph",
            action="store_true",
            help="Print the group tree instead of the inventory, like ansible-inventory --graph.",
        )

    def handle(self, *args, **options):
        environment = _resolve(Environment, options["environment"], "environment")
        client = _resolve(Client, options["client"], "client")
        selection = {
            "environment": environment,
            "client": client,
            "include_inactive": options["include_inactive"],
        }

        if options["graph"]:
            self.stdout.write(graph(build(**selection)))
            return

        content = render(**selection)
        if not options["output"]:
            self.stdout.write(content)
            return

        path = Path(options["output"]).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        hosts = len(build(**selection)["all"]["hosts"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {hosts} hosts to {path}"))


def _resolve(model, value, label):
    """Look *value* up by slug or name, so either is accepted on the CLI."""
    if not value:
        return None
    found = model.objects.filter(slug=value).first() or model.objects.filter(name=value).first()
    if found is None:
        raise CommandError(f"No {label} called {value!r}.")
    return found

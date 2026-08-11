"""Create (or refresh) the system roles the platform ships with."""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from authentication.models import Role

# slug -> (name, description, admin access, superuser, permission selector)
SYSTEM_ROLES = {
    "administrator": (
        "Administrator",
        "Full control of the platform, including user and role management.",
        True,
        True,
        "all",
    ),
    "operator": (
        "Operator",
        "Runs day-to-day operations and reviews platform activity.",
        False,
        False,
        "operate",
    ),
    "developer": (
        "Developer",
        "Works with automation content and platform configuration.",
        False,
        False,
        "operate",
    ),
    "auditor": (
        "Auditor",
        "Read-only access to the audit trail and security events.",
        False,
        False,
        "read",
    ),
    "viewer": (
        "Viewer",
        "Read-only access to platform state.",
        False,
        False,
        "read",
    ),
}

PLATFORM_APPS = ["audit", "security", "ipintel", "settings_platform", "authentication"]


class Command(BaseCommand):
    help = "Create the system roles. Idempotent: existing roles are updated, never duplicated."

    @transaction.atomic
    def handle(self, *args, **options):
        readable = Permission.objects.filter(
            content_type__app_label__in=PLATFORM_APPS, codename__startswith="view_"
        )
        operable = Permission.objects.filter(content_type__app_label__in=PLATFORM_APPS).exclude(
            codename__startswith="delete_"
        )

        for slug, (name, desc, admin, superuser, selector) in SYSTEM_ROLES.items():
            role, created = Role.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "grants_admin_access": admin,
                    "grants_superuser": superuser,
                    "is_system": True,
                },
            )
            if selector == "all":
                role.permissions.set(Permission.objects.all())
            elif selector == "operate":
                role.permissions.set(operable)
            else:
                role.permissions.set(readable)

            self.stdout.write(f"  {'created' if created else 'updated'}  {role.name}")

        self.stdout.write(self.style.SUCCESS(f"{len(SYSTEM_ROLES)} system roles ready."))

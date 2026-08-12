"""Create (or refresh) the system roles the platform ships with."""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import models, transaction

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

#: What an operator manages day to day. Full CRUD here, deletion included: an
#: operator who can register a server but never remove it is not an operator,
#: and every list in the interface hides its Delete action behind exactly this.
OPERATIONAL_APPS = [
    "infrastructure",
    "credentials",
    "automation",
    "jobs",
]

#: Platform internals. Read-only for everyone but an administrator — these
#: describe what happened and who may do what, and are not day-to-day work.
GOVERNANCE_APPS = [
    "audit",
    "security",
    "ipintel",
    "settings_platform",
    "authentication",
]

PLATFORM_APPS = OPERATIONAL_APPS + GOVERNANCE_APPS

#: Never granted through a role, to anybody. A trail somebody can delete is
#: not a trail. Removing history stays a database operation, deliberate and
#: outside the product.
NEVER_GRANTED = ["delete_auditevent"]


class Command(BaseCommand):
    help = "Create the system roles. Idempotent: existing roles are updated, never duplicated."

    @transaction.atomic
    def handle(self, *args, **options):
        grantable = Permission.objects.exclude(codename__in=NEVER_GRANTED)

        readable = grantable.filter(
            content_type__app_label__in=PLATFORM_APPS, codename__startswith="view_"
        )
        # Everything on what they operate, plus visibility into the rest.
        operable = grantable.filter(
            models.Q(content_type__app_label__in=OPERATIONAL_APPS)
            | models.Q(content_type__app_label__in=GOVERNANCE_APPS, codename__startswith="view_")
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
                role.permissions.set(grantable)
            elif selector == "operate":
                role.permissions.set(operable)
            else:
                role.permissions.set(readable)

            self.stdout.write(f"  {'created' if created else 'updated'}  {role.name}")

        self.stdout.write(self.style.SUCCESS(f"{len(SYSTEM_ROLES)} system roles ready."))

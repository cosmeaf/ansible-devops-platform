"""Create the initial accounts described by the environment.

Two distinct accounts, because they serve different purposes:

* the **operator** account may reach Django Admin (Administrator role);
* the **platform** account may not — it uses the platform's own management
  interface only (Operator role).

Idempotent: an existing account is never given a new password unless
``--force-password`` is passed.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from authentication.models import Role, UserRole


class Command(BaseCommand):
    help = "Create the initial operator and platform accounts from the environment."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset the password of an existing account to the configured value.",
        )

    def _ensure(self, username, email, password, role_slug, force):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        if created or force:
            user.set_password(password)
            user.save()

        role = Role.objects.filter(slug=role_slug).first()
        if role:
            UserRole.objects.get_or_create(user=user, role=role)

        state = "created" if created else ("password reset" if force else "unchanged")
        admin = "yes" if role and role.grants_admin_access else "no"
        self.stdout.write(f"  {username:<12} {state:<16} role={role_slug:<14} admin={admin}")
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force_password"]

        operator_user = os.environ.get("INITIAL_ADMIN_USERNAME", "admin")
        operator_pass = os.environ.get("INITIAL_ADMIN_PASSWORD")
        platform_user = os.environ.get("INITIAL_PLATFORM_USERNAME", "ansible")
        platform_pass = os.environ.get("INITIAL_PLATFORM_PASSWORD")

        if not operator_pass:
            self.stderr.write("INITIAL_ADMIN_PASSWORD is not set; skipping operator account.")
        else:
            self._ensure(
                operator_user,
                os.environ.get("INITIAL_ADMIN_EMAIL", "admin@localhost"),
                operator_pass,
                "administrator",
                force,
            )

        if not platform_pass:
            self.stdout.write("  INITIAL_PLATFORM_PASSWORD not set; skipping platform account.")
        else:
            self._ensure(
                platform_user,
                os.environ.get("INITIAL_PLATFORM_EMAIL", "ansible@localhost"),
                platform_pass,
                "operator",
                force,
            )

        self.stdout.write(self.style.SUCCESS("Initial accounts ready."))

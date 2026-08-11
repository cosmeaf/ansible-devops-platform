"""Role-based access control.

Authorisation is governed by roles, not by hand-toggled flags. ``is_staff`` and
``is_superuser`` are *derived* from a user's roles and resynchronised whenever
an assignment changes — an operator never sets them directly.

Django Admin is an operator-only interface, never product surface, so the role
that opens it is explicit and separate from ordinary platform access. See
docs/adr/0011-role-based-access-control.md.
"""

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models

from commun.models import BaseModel


class Role(BaseModel):
    """A named set of permissions that can be granted to users."""

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)

    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
        help_text="Model permissions granted to every holder of this role.",
    )

    #: Opens Django Admin. Deliberately narrow: the admin is an operator
    #: backdoor for running the platform, not part of the product.
    grants_admin_access = models.BooleanField(
        default=False,
        help_text="Holders may sign in to Django Admin (maps to is_staff).",
    )
    #: Unrestricted access. Should belong to exactly one role.
    grants_superuser = models.BooleanField(
        default=False,
        help_text="Holders bypass all permission checks (maps to is_superuser).",
    )
    #: System roles ship with the platform and must not be deleted, or a
    #: deployment could be left with no way back in.
    is_system = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "role"
        verbose_name_plural = "roles"

    def __str__(self) -> str:
        return self.name


class UserRole(BaseModel):
    """Assignment of a :class:`Role` to a user, with provenance."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="roles_assigned",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "role assignment"
        verbose_name_plural = "role assignments"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role_assignment")
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.role}"


def roles_for(user) -> models.QuerySet:
    """Return the roles currently assigned to *user*."""
    if not user or user.is_anonymous:
        return Role.objects.none()
    return Role.objects.filter(assignments__user=user)


def sync_flags(user) -> None:
    """Recompute ``is_staff`` / ``is_superuser`` from *user*'s roles.

    Called whenever an assignment changes. Flags are never authoritative on
    their own; roles are.
    """
    roles = roles_for(user)
    is_staff = roles.filter(grants_admin_access=True).exists()
    is_superuser = roles.filter(grants_superuser=True).exists()

    if user.is_staff != is_staff or user.is_superuser != is_superuser:
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save(update_fields=["is_staff", "is_superuser"])

"""Role-based access control.

Authorisation must come from roles. These tests exist to stop anyone
reintroducing hand-set ``is_staff`` as a source of truth.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command

from authentication.models import Role, UserRole, roles_for


@pytest.fixture
def seeded_roles(db):
    call_command("seed_roles")
    return Role.objects.all()


@pytest.mark.django_db
def test_seed_roles_creates_the_system_roles(seeded_roles):
    slugs = set(Role.objects.values_list("slug", flat=True))

    assert {"administrator", "operator", "developer", "auditor", "viewer"} <= slugs
    assert Role.objects.filter(is_system=True).count() == 5


@pytest.mark.django_db
def test_seed_roles_is_idempotent(seeded_roles):
    call_command("seed_roles")
    call_command("seed_roles")

    assert Role.objects.filter(slug="administrator").count() == 1


@pytest.mark.django_db
def test_only_administrator_grants_admin_and_superuser(seeded_roles):
    assert list(Role.objects.filter(grants_admin_access=True).values_list("slug", flat=True)) == [
        "administrator"
    ]
    assert list(Role.objects.filter(grants_superuser=True).values_list("slug", flat=True)) == [
        "administrator"
    ]


@pytest.mark.django_db
def test_assigning_administrator_derives_the_flags(user, seeded_roles):
    assert user.is_staff is False

    UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()

    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_revoking_the_role_removes_the_derived_flags(user, seeded_roles):
    assignment = UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()
    assert user.is_staff is True

    assignment.delete()
    user.refresh_from_db()

    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_operator_role_never_grants_admin_access(user, seeded_roles):
    """The platform user must not be able to reach Django Admin."""
    UserRole.objects.create(user=user, role=Role.objects.get(slug="operator"))
    user.refresh_from_db()

    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_a_user_cannot_hold_the_same_role_twice(user, seeded_roles):
    role = Role.objects.get(slug="viewer")
    UserRole.objects.create(user=user, role=role)

    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        UserRole.objects.create(user=user, role=role)


@pytest.mark.django_db
def test_permissions_are_resolved_through_roles(user, seeded_roles):
    assert user.has_perm("audit.view_auditevent") is False

    UserRole.objects.create(user=user, role=Role.objects.get(slug="viewer"))
    user = get_user_model().objects.get(pk=user.pk)  # drop the permission cache

    assert user.has_perm("audit.view_auditevent") is True


@pytest.mark.django_db
def test_viewer_gets_read_permissions_but_not_delete(user, seeded_roles):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="viewer"))
    user = get_user_model().objects.get(pk=user.pk)

    assert user.has_perm("audit.view_auditevent") is True
    assert user.has_perm("audit.delete_auditevent") is False
    assert user.has_perm("audit.add_auditevent") is False


@pytest.mark.django_db
def test_roles_for_returns_assigned_roles(user, seeded_roles):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="auditor"))

    assert [r.slug for r in roles_for(user)] == ["auditor"]


@pytest.mark.django_db
def test_roles_for_an_anonymous_user_is_empty(seeded_roles):
    from django.contrib.auth.models import AnonymousUser

    assert roles_for(AnonymousUser()).count() == 0


@pytest.mark.django_db
def test_custom_role_grants_exactly_its_permissions(user):
    role = Role.objects.create(slug="reporter", name="Reporter")
    role.permissions.add(Permission.objects.get(codename="view_auditevent"))
    UserRole.objects.create(user=user, role=role)
    user = get_user_model().objects.get(pk=user.pk)

    assert user.has_perm("audit.view_auditevent") is True
    assert user.has_perm("security.view_securityevent") is False


@pytest.mark.django_db
def test_role_str_is_its_name():
    assert str(Role.objects.create(slug="x", name="Example")) == "Example"

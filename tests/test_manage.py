"""The platform's own management interface.

Two invariants are load-bearing here:

* the management UI never routes a user to Django Admin;
* every screen is gated by a role-derived permission.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from authentication.models import Role, UserRole

SCREENS = [
    "manage:overview",
    "manage:audit",
    "manage:security",
    "manage:ipintel",
    "manage:settings",
    "manage:users",
    "manage:roles",
]


@pytest.fixture
def seeded(db):
    call_command("seed_roles")


@pytest.fixture
def administrator(user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_every_screen_requires_authentication(client, route):
    response = client.get(reverse(route))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_administrator_reaches_every_screen(client, administrator, route):
    client.force_login(administrator)

    assert client.get(reverse(route)).status_code == 200


@pytest.mark.django_db
def test_a_user_without_roles_is_denied_the_gated_screens(client, user, seeded):
    client.force_login(user)

    assert client.get(reverse("manage:overview")).status_code == 200  # ungated
    assert client.get(reverse("manage:audit")).status_code == 403
    assert client.get(reverse("manage:users")).status_code == 403


@pytest.mark.django_db
def test_viewer_may_read_audit_but_not_manage_users(client, user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="viewer"))
    client.force_login(user)

    assert client.get(reverse("manage:audit")).status_code == 200
    assert client.get(reverse("manage:users")).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_no_management_screen_links_to_django_admin(client, administrator, route):
    """Django Admin is an operator backdoor, never product surface."""
    client.force_login(administrator)

    body = client.get(reverse(route)).content.decode()

    assert 'href="/admin/' not in body
    assert "Django Admin" not in body


@pytest.mark.django_db
def test_the_landing_page_does_not_link_to_django_admin(client, administrator):
    client.force_login(administrator)

    body = client.get(reverse("dashboard")).content.decode()

    assert 'href="/admin/' not in body


@pytest.mark.django_db
def test_the_login_page_does_not_link_to_django_admin(client):
    assert 'href="/admin/' not in client.get(reverse("login")).content.decode()


@pytest.mark.django_db
def test_audit_screen_filters_by_username(client, administrator):
    from audit.models import AuditEvent

    AuditEvent.objects.create(module="m", action="LOGIN", username_snapshot="alice")
    AuditEvent.objects.create(module="m", action="LOGIN", username_snapshot="bob")
    client.force_login(administrator)

    body = client.get(reverse("manage:audit"), {"q": "alice"}).content.decode()

    assert "alice" in body
    assert "bob" not in body


@pytest.mark.django_db
def test_secret_settings_are_masked_in_the_interface(client, administrator):
    from settings_platform.models import PlatformSetting

    PlatformSetting.objects.create(
        category="smtp", key="password", value={"v": "s3nsitive"}, is_secret=True
    )
    client.force_login(administrator)

    body = client.get(reverse("manage:settings")).content.decode()

    assert "s3nsitive" not in body
    assert "[REDACTED]" in body


@pytest.mark.django_db
def test_templates_render_without_a_stray_template_comment(client):
    """A multi-line {# #} is not a comment in Django and leaks to the page."""
    body = client.get(reverse("login")).content.decode()

    assert "Styles are inlined" not in body
    assert "{#" not in body

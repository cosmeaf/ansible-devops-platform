"""Authentication flow as it exists today.

Module 1 ships Django's session authentication and admin only. RBAC, password
reset delivery and forced password change are roadmap items (see ROADMAP.md);
these tests assert the current behaviour rather than an aspirational one.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from tests.conftest import TEST_PASSWORD


@pytest.mark.django_db
def test_login_page_is_reachable_anonymously(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_valid_credentials_start_a_session(client, user):
    response = client.post(reverse("login"), {"username": user.username, "password": TEST_PASSWORD})

    assert response.status_code == 302
    assert client.session.get("_auth_user_id") == str(user.pk)


@pytest.mark.django_db
def test_invalid_credentials_do_not_start_a_session(client, user):
    response = client.post(
        reverse("login"), {"username": user.username, "password": "wrong-password"}
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_clears_the_session(authenticated_client):
    authenticated_client.post(reverse("logout"))

    assert "_auth_user_id" not in authenticated_client.session


@pytest.mark.django_db
def test_admin_redirects_anonymous_users_to_login(client):
    response = client.get("/admin/")

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_admin_is_reachable_by_a_superuser(admin_user, client):
    client.force_login(admin_user)

    assert client.get("/admin/").status_code == 200


@pytest.mark.django_db
def test_non_staff_user_cannot_reach_admin(authenticated_client):
    response = authenticated_client.get("/admin/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_passwords_are_hashed_never_stored_in_clear():
    user = get_user_model().objects.create_user(username="hashcheck", password=TEST_PASSWORD)

    assert TEST_PASSWORD not in user.password
    assert user.password.split("$")[0] in {"pbkdf2_sha256", "argon2", "bcrypt_sha256"}
    assert user.check_password(TEST_PASSWORD) is True


@pytest.mark.django_db
def test_dashboard_renders_for_anonymous_and_authenticated_users(client, user):
    assert client.get(reverse("dashboard")).status_code == 200

    client.force_login(user)
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert user.username in response.content.decode()

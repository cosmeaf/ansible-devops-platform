"""Shared fixtures.

Tests run against real PostgreSQL — the project does not support SQLite, and
substituting it here would hide the incompatibilities these tests exist to
catch.
"""

import pytest
from django.contrib.auth import get_user_model

# Any password used below is a throwaway fixture value, never a real credential.
TEST_PASSWORD = "fixture-password-not-a-secret-1"


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="tester",
        email="tester@example.invalid",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_superuser(
        username="root-tester",
        email="root@example.invalid",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client

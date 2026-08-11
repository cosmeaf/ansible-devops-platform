"""Health endpoint behaviour."""

import json
from unittest import mock

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_healthy_when_all_dependencies_answer(client):
    with mock.patch("core.views._check_redis", return_value=True):
        response = client.get(reverse("health"))

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["status"] == "healthy"
    assert payload["database"] is True
    assert payload["redis"] is True


@pytest.mark.django_db
def test_health_returns_503_when_redis_is_down(client):
    with mock.patch("core.views._check_redis", return_value=False):
        response = client.get(reverse("health"))

    assert response.status_code == 503
    assert json.loads(response.content)["status"] == "degraded"


@pytest.mark.django_db
def test_health_returns_503_when_database_is_down(client):
    with (
        mock.patch("core.views._check_database", return_value=False),
        mock.patch("core.views._check_redis", return_value=True),
    ):
        response = client.get(reverse("health"))

    assert response.status_code == 503
    assert json.loads(response.content)["database"] is False


@pytest.mark.django_db
def test_health_requires_no_authentication(client):
    """Orchestrators probe this endpoint without credentials."""
    with mock.patch("core.views._check_redis", return_value=True):
        assert client.get(reverse("health")).status_code == 200


@pytest.mark.django_db
def test_health_rejects_non_get_methods(client):
    assert client.post(reverse("health")).status_code == 405


@pytest.mark.django_db
def test_health_never_leaks_connection_details(client):
    """A failing dependency must not expose hosts, DSNs or credentials."""
    from django.conf import settings

    with mock.patch("core.views._check_redis", return_value=False):
        body = client.get(reverse("health")).content.decode()

    assert settings.DATABASES["default"]["PASSWORD"] not in body
    assert settings.DATABASES["default"]["HOST"] not in body
    assert settings.REDIS_HOST not in body
    assert "postgres://" not in body and "redis://" not in body


@pytest.mark.django_db
def test_health_reports_platform_version(client):
    from django.conf import settings

    with mock.patch("core.views._check_redis", return_value=True):
        payload = json.loads(client.get(reverse("health")).content)

    assert payload["version"] == settings.VERSION

"""Security event model and platform hardening settings."""

import pytest
from django.conf import settings

from security.models import SecurityEvent, SecurityEventType, SecuritySeverity


@pytest.mark.django_db
def test_security_event_defaults_to_info_severity():
    event = SecurityEvent.objects.create(event_type=SecurityEventType.FAILED_LOGIN)

    assert event.severity == SecuritySeverity.INFO
    assert event.metadata == {}


@pytest.mark.django_db
def test_security_event_survives_user_deletion(user):
    event = SecurityEvent.objects.create(
        event_type=SecurityEventType.FAILED_LOGIN, user=user, source_ip="203.0.113.9"
    )

    user.delete()
    event.refresh_from_db()

    assert event.user is None
    assert event.source_ip == "203.0.113.9"


@pytest.mark.django_db
def test_security_event_ordering_is_newest_first():
    older = SecurityEvent.objects.create(event_type=SecurityEventType.SESSION_EVENT)
    newer = SecurityEvent.objects.create(event_type=SecurityEventType.BLOCKED_IP)

    assert list(SecurityEvent.objects.all()) == [newer, older]


@pytest.mark.django_db
def test_security_event_str_includes_type_and_severity():
    event = SecurityEvent.objects.create(
        event_type=SecurityEventType.BLOCKED_IP,
        severity=SecuritySeverity.HIGH,
        source_ip="198.51.100.4",
    )

    assert str(event) == "BLOCKED_IP [HIGH] from 198.51.100.4"


def test_session_cookies_are_httponly_and_samesite():
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"


def test_clickjacking_and_sniffing_protections_are_enabled():
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert settings.SECURE_REFERRER_POLICY == "same-origin"


def test_password_policy_requires_a_meaningful_minimum_length():
    validators = {v["NAME"].rsplit(".", 1)[-1]: v for v in settings.AUTH_PASSWORD_VALIDATORS}

    assert "CommonPasswordValidator" in validators
    assert validators["MinimumLengthValidator"]["OPTIONS"]["min_length"] >= 12


def test_cors_denies_all_origins_by_default():
    """Module 1 ships no browser client, so nothing should be allow-listed."""
    assert settings.CORS_ALLOWED_ORIGINS == []


def test_drf_requires_authentication_by_default():
    defaults = settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]

    assert defaults == ["rest_framework.permissions.IsAuthenticated"]


def test_drf_throttling_is_configured():
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    assert rates["anon"] and rates["user"]


def test_database_is_postgresql():
    """SQLite must never silently become the backend — not even under test."""
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"

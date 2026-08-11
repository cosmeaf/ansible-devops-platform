"""Audit model and redaction behaviour."""

import pytest

from audit.models import AuditAction, AuditEvent, AuditResult
from audit.sanitizers import REDACTED, is_sensitive_key, sanitize, sanitize_headers


@pytest.mark.django_db
def test_audit_event_persists_with_defaults():
    event = AuditEvent.objects.create(module="authentication", action=AuditAction.LOGIN)

    assert event.result == AuditResult.SUCCESS
    assert event.uuid is not None
    assert event.created_at is not None


@pytest.mark.django_db
def test_audit_event_snapshots_username_so_trail_survives_deletion(user):
    event = AuditEvent.objects.create(user=user, module="authentication", action=AuditAction.LOGIN)
    assert event.username_snapshot == "tester"

    user.delete()
    event.refresh_from_db()

    assert event.user is None
    assert event.username_snapshot == "tester"


@pytest.mark.django_db
def test_audit_event_redacts_passwords_on_save():
    event = AuditEvent.objects.create(
        module="authentication",
        action=AuditAction.UPDATE,
        new_value={"username": "admin", "password": "hunter2"},
    )
    event.refresh_from_db()

    assert event.new_value["username"] == "admin"
    assert event.new_value["password"] == REDACTED


@pytest.mark.django_db
def test_audit_event_redacts_nested_and_listed_secrets():
    event = AuditEvent.objects.create(
        module="settings",
        action=AuditAction.UPDATE,
        previous_value={"conn": {"api_key": "abc", "host": "db"}},
        metadata={"headers": [{"Authorization": "Bearer x"}]},
    )
    event.refresh_from_db()

    assert event.previous_value["conn"]["api_key"] == REDACTED
    assert event.previous_value["conn"]["host"] == "db"
    assert event.metadata["headers"][0]["Authorization"] == REDACTED


@pytest.mark.django_db
def test_audit_event_ordering_is_newest_first():
    older = AuditEvent.objects.create(module="a", action=AuditAction.READ)
    newer = AuditEvent.objects.create(module="b", action=AuditAction.READ)

    assert list(AuditEvent.objects.all()) == [newer, older]


@pytest.mark.django_db
def test_audit_event_str_is_human_readable(user):
    event = AuditEvent.objects.create(user=user, module="authentication", action=AuditAction.LOGIN)
    assert str(event) == "LOGIN authentication by tester (SUCCESS)"


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "PASSWORD",
        "new_password",
        "secret",
        "api_key",
        "APIKey",
        "private_key",
        "Cookie",
        "Authorization",
        "csrfmiddlewaretoken",
        "encryption_key",
        "passphrase",
    ],
)
def test_sensitive_keys_are_recognised(key):
    assert is_sensitive_key(key) is True


@pytest.mark.parametrize("key", ["username", "module", "host", "id", "count", 42, None])
def test_ordinary_keys_are_not_redacted(key):
    assert is_sensitive_key(key) is False


def test_sanitize_leaves_scalars_untouched():
    assert sanitize("plain") == "plain"
    assert sanitize(7) == 7
    assert sanitize(None) is None


def test_sanitize_preserves_tuple_type():
    assert sanitize(("a", "b")) == ("a", "b")


def test_sanitize_stops_at_max_depth():
    """A pathologically deep payload is truncated rather than recursed forever."""
    payload: dict = {}
    cursor = payload
    for _ in range(40):
        cursor["next"] = {}
        cursor = cursor["next"]

    result = sanitize(payload)

    cursor = result
    depth = 0
    while isinstance(cursor, dict) and "next" in cursor:
        cursor = cursor["next"]
        depth += 1
    assert cursor == REDACTED
    assert depth < 40


def test_sanitize_headers_keeps_names_and_redacts_values():
    cleaned = sanitize_headers({"Cookie": "sid=1", "User-Agent": "curl/8"})

    assert cleaned == {"Cookie": REDACTED, "User-Agent": "curl/8"}

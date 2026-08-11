"""Credential storage.

The invariant under test: a stored secret is never returned. Not by the API,
not by the admin, not by str(), not by the audit trail.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse

from authentication.models import Role, UserRole
from credentials.crypto import DecryptionError, decrypt, encrypt
from credentials.models import Credential, CredentialType

#: A marker the ciphertext must never contain. Deliberately not shaped like
#: a PEM block: the test needs something recognisable, not key material.
MARKER = "RECOGNISABLE-PLAINTEXT-MARKER"
SECRET = f"fixture credential {MARKER} not a real key"


@pytest.fixture
def administrator(user, db):
    call_command("seed_roles")
    UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()
    return user


@pytest.fixture
def credential(db):
    c = Credential(name="prod-ssh", type=CredentialType.SSH_PRIVATE_KEY, username="ansible")
    c.set_secret(SECRET)
    c.save()
    return c


# --- crypto ---------------------------------------------------------------


def test_encryption_round_trips():
    assert decrypt(encrypt(SECRET)) == SECRET


def test_ciphertext_does_not_contain_the_plaintext():
    assert MARKER not in encrypt(SECRET)


def test_encrypting_twice_gives_different_ciphertext():
    """A random IV per encryption; identical secrets must not look identical."""
    assert encrypt(SECRET) != encrypt(SECRET)


def test_tampered_ciphertext_is_rejected():
    ciphertext = encrypt(SECRET)

    with pytest.raises(DecryptionError):
        decrypt(ciphertext[:-8] + "AAAAAAAA")


def test_empty_secret_is_refused():
    credential = Credential(name="x", type=CredentialType.SSH_PASSWORD)

    with pytest.raises(ValueError):
        credential.set_secret("")


# --- model ----------------------------------------------------------------


@pytest.mark.django_db
def test_secret_is_stored_encrypted_not_in_clear(credential):
    credential.refresh_from_db()

    assert credential.encrypted_secret != SECRET
    assert "OPENSSH" not in credential.encrypted_secret
    assert credential.has_secret is True


@pytest.mark.django_db
def test_secret_can_be_revealed_only_deliberately(credential):
    assert credential.reveal_secret() == SECRET


@pytest.mark.django_db
def test_str_never_leaks_the_secret(credential):
    assert SECRET not in str(credential)
    assert str(credential) == "prod-ssh (SSH private key)"


@pytest.mark.django_db
def test_credential_names_are_unique(credential):
    from django.db.utils import IntegrityError

    duplicate = Credential(name="prod-ssh", type=CredentialType.SSH_PASSWORD)
    duplicate.set_secret("x")

    with pytest.raises(IntegrityError):
        duplicate.save()


@pytest.mark.django_db
def test_use_is_a_distinct_permission_from_view():
    """An operator may use a credential without being able to read it."""
    from django.contrib.auth.models import Permission

    assert Permission.objects.filter(codename="use_credential").exists()
    assert Permission.objects.filter(codename="view_credential").exists()


# --- API ------------------------------------------------------------------


@pytest.mark.django_db
def test_api_never_returns_the_secret(client, administrator, credential):
    client.force_login(administrator)

    response = client.get(reverse("credential-list"))
    body = response.content.decode()

    assert response.status_code == 200
    assert SECRET not in body
    assert "OPENSSH" not in body
    assert credential.encrypted_secret not in body


@pytest.mark.django_db
def test_api_detail_never_returns_the_secret(client, administrator, credential):
    client.force_login(administrator)

    body = client.get(reverse("credential-detail", args=[credential.uuid])).content.decode()

    assert SECRET not in body
    assert "encrypted_secret" not in body


@pytest.mark.django_db
def test_api_can_create_a_credential(client, administrator):
    client.force_login(administrator)

    response = client.post(
        reverse("credential-list"),
        {"name": "new-key", "type": "SSH_PASSWORD", "username": "deploy", "secret": "hunter2"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert "hunter2" not in response.content.decode()
    assert Credential.objects.get(name="new-key").reveal_secret() == "hunter2"


@pytest.mark.django_db
def test_api_refuses_a_credential_without_a_secret(client, administrator):
    client.force_login(administrator)

    response = client.post(
        reverse("credential-list"),
        {"name": "no-secret", "type": "SSH_PASSWORD"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_updating_without_a_secret_keeps_the_existing_one(client, administrator, credential):
    client.force_login(administrator)

    response = client.patch(
        reverse("credential-detail", args=[credential.uuid]),
        {"description": "rotated docs"},
        content_type="application/json",
    )

    assert response.status_code == 200
    credential.refresh_from_db()
    assert credential.reveal_secret() == SECRET


@pytest.mark.django_db
def test_api_requires_authentication(client, credential):
    assert client.get(reverse("credential-list")).status_code in (401, 403)


@pytest.mark.django_db
def test_creating_a_credential_writes_an_audit_event_without_the_secret(client, administrator):
    from audit.models import AuditEvent

    client.force_login(administrator)
    client.post(
        reverse("credential-list"),
        {"name": "audited", "type": "SSH_PASSWORD", "secret": "topsecret"},
        content_type="application/json",
    )

    event = AuditEvent.objects.filter(module="credentials").first()

    assert event is not None
    assert "topsecret" not in str(event.new_value)

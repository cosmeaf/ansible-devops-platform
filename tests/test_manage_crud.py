"""Every managed object can be created, edited and deleted from the web."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from audit.models import AuditAction, AuditEvent
from credentials.models import Credential
from infrastructure.models import Client, Environment, Server, ServerGroup


@pytest.fixture
def manager(db):
    """A user holding every infrastructure and credential permission."""
    user = get_user_model().objects.create_user("manager", password="fixture-password-not-a-secret-1")
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label__in=["infrastructure", "credentials"])
    )
    return user


@pytest.fixture
def logged_in(client, manager):
    client.force_login(manager)
    return client


# --- the screens exist and are reachable ------------------------------------


@pytest.mark.parametrize(
    "route",
    [
        "manage:servers",
        "manage:server-create",
        "manage:groups",
        "manage:group-create",
        "manage:environments",
        "manage:environment-create",
        "manage:clients",
        "manage:client-create",
        "manage:credentials",
        "manage:credential-create",
    ],
)
def test_every_management_screen_answers(logged_in, route):
    assert logged_in.get(reverse(route)).status_code == 200


def test_the_group_list_offers_a_way_to_create_one(logged_in):
    """A list with no create button is a dead end."""
    body = logged_in.get(reverse("manage:groups")).content.decode()

    assert reverse("manage:group-create") in body


def test_the_environment_list_offers_a_way_to_create_one(logged_in):
    body = logged_in.get(reverse("manage:environments")).content.decode()

    assert reverse("manage:environment-create") in body


# --- create -----------------------------------------------------------------


def test_creating_a_group(logged_in):
    logged_in.post(reverse("manage:group-create"), {"name": "webservers", "description": ""})

    assert ServerGroup.objects.filter(name="webservers").exists()


def test_creating_a_server(logged_in):
    logged_in.post(
        reverse("manage:server-create"),
        {
            "name": "web01",
            "description": "",
            "hostname": "",
            "primary_ip": "198.51.100.10",
            "connection_method": "SSH",
            "ssh_port": 22,
            "ansible_user": "ansible",
            "operating_system": "LINUX",
            "active": "on",
        },
    )

    assert Server.objects.filter(name="web01").exists()


# --- edit -------------------------------------------------------------------


def test_editing_a_group(logged_in):
    group = ServerGroup.objects.create(name="webservers")

    logged_in.post(
        reverse("manage:group-edit", args=[group.uuid]),
        {"name": "frontends", "description": "renamed"},
    )

    group.refresh_from_db()
    assert group.name == "frontends"


def test_editing_an_environment(logged_in):
    environment = Environment.objects.create(name="Staging")

    logged_in.post(
        reverse("manage:environment-edit", args=[environment.uuid]),
        {"name": "Staging", "description": "", "require_check_mode": "on", "active": "on"},
    )

    environment.refresh_from_db()
    assert environment.require_check_mode is True


def test_editing_a_client(logged_in):
    client_record = Client.objects.create(name="Avaliza")

    logged_in.post(
        reverse("manage:client-edit", args=[client_record.uuid]),
        {"name": "Avaliza", "description": "", "contact_email": "ops@example.com", "active": "on"},
    )

    client_record.refresh_from_db()
    assert client_record.contact_email == "ops@example.com"


def test_editing_a_credential_without_a_secret_keeps_the_stored_one(logged_in):
    credential = Credential.objects.create(name="deploy", type="SSH_PRIVATE_KEY", username="root")
    credential.set_secret("the-original-key")
    credential.save()

    logged_in.post(
        reverse("manage:credential-edit", args=[credential.uuid]),
        {
            "name": "deploy",
            "description": "renamed",
            "type": "SSH_PRIVATE_KEY",
            "username": "root",
            "secret": "",
        },
    )

    credential.refresh_from_db()
    assert credential.description == "renamed"
    assert credential.reveal_secret() == "the-original-key"


# --- delete -----------------------------------------------------------------


def test_deleting_asks_before_it_removes_anything(logged_in):
    group = ServerGroup.objects.create(name="webservers")

    response = logged_in.get(reverse("manage:group-delete", args=[group.uuid]))

    assert response.status_code == 200
    assert ServerGroup.objects.filter(pk=group.pk).exists()


def test_deleting_a_group_on_post(logged_in):
    group = ServerGroup.objects.create(name="webservers")

    logged_in.post(reverse("manage:group-delete", args=[group.uuid]))

    assert not ServerGroup.objects.filter(pk=group.pk).exists()


def test_deleting_a_server(logged_in):
    server = Server.objects.create(name="web01", primary_ip="198.51.100.10")

    logged_in.post(reverse("manage:server-delete", args=[server.uuid]))

    assert not Server.objects.filter(pk=server.pk).exists()


def test_deleting_a_credential(logged_in):
    credential = Credential.objects.create(name="deploy", type="SSH_PRIVATE_KEY", username="root")
    credential.set_secret("k")
    credential.save()

    logged_in.post(reverse("manage:credential-delete", args=[credential.uuid]))

    assert not Credential.objects.filter(pk=credential.pk).exists()


def test_an_environment_still_holding_servers_is_not_deleted(logged_in):
    """PROTECT would be a 500; the operator gets told what to do instead."""
    environment = Environment.objects.create(name="Production")
    Server.objects.create(name="web01", primary_ip="198.51.100.10", environment=environment)

    response = logged_in.post(
        reverse("manage:environment-delete", args=[environment.uuid]), follow=True
    )

    assert response.status_code == 200
    assert Environment.objects.filter(pk=environment.pk).exists()
    assert "still has servers attached" in response.content.decode()


def test_the_confirmation_says_how_many_servers_are_affected(logged_in):
    client_record = Client.objects.create(name="Avaliza")
    Server.objects.create(name="web01", primary_ip="198.51.100.10", client=client_record)

    body = logged_in.get(
        reverse("manage:client-delete", args=[client_record.uuid])
    ).content.decode()

    assert "1 server" in body


def test_a_deletion_is_recorded_in_the_audit_trail(logged_in):
    group = ServerGroup.objects.create(name="webservers")

    logged_in.post(reverse("manage:group-delete", args=[group.uuid]))

    event = AuditEvent.objects.filter(action=AuditAction.DELETE).latest("created_at")
    assert event.resource_type == "ServerGroup"
    assert event.new_value == {"name": "webservers"}


# --- permissions ------------------------------------------------------------


def test_a_reader_cannot_delete(client, db):
    reader = get_user_model().objects.create_user("reader", password="fixture-password-not-a-secret-1")
    reader.user_permissions.add(Permission.objects.get(codename="view_servergroup"))
    group = ServerGroup.objects.create(name="webservers")
    client.force_login(reader)

    response = client.post(reverse("manage:group-delete", args=[group.uuid]))

    assert response.status_code == 403
    assert ServerGroup.objects.filter(pk=group.pk).exists()


def test_a_reader_sees_no_delete_link(client, db):
    reader = get_user_model().objects.create_user("reader2", password="fixture-password-not-a-secret-1")
    reader.user_permissions.add(Permission.objects.get(codename="view_servergroup"))
    group = ServerGroup.objects.create(name="webservers")
    client.force_login(reader)

    body = client.get(reverse("manage:groups")).content.decode()

    assert reverse("manage:group-delete", args=[group.uuid]) not in body

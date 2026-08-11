"""REST API for infrastructure: permissions, validation and audit."""

import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from audit.models import AuditEvent
from authentication.models import Role, UserRole
from infrastructure.models import Client, Environment, Server, ServerGroup


@pytest.fixture
def seeded(db):
    call_command("seed_roles")


@pytest.fixture
def administrator(user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()
    return user


@pytest.fixture
def viewer(django_user_model, seeded):
    person = django_user_model.objects.create_user(username="ro", password="x-not-a-secret-1")
    UserRole.objects.create(user=person, role=Role.objects.get(slug="viewer"))
    person.refresh_from_db()
    return person


@pytest.mark.django_db
def test_api_requires_authentication(client):
    assert client.get(reverse("server-list")).status_code in (401, 403)


@pytest.mark.django_db
def test_administrator_can_register_a_server(client, administrator):
    client.force_login(administrator)

    response = client.post(
        reverse("server-list"),
        {"name": "web01", "primary_ip": "10.0.0.5", "ansible_user": "ansible"},
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    assert Server.objects.filter(name="web01").exists()


@pytest.mark.django_db
def test_a_registered_server_records_who_created_it(client, administrator):
    client.force_login(administrator)
    client.post(
        reverse("server-list"),
        {"name": "web01", "primary_ip": "10.0.0.5"},
        content_type="application/json",
    )

    assert Server.objects.get(name="web01").created_by == administrator


@pytest.mark.django_db
def test_a_server_must_be_addressable(client, administrator):
    """Neither an IP nor a hostname means Ansible cannot reach it."""
    client.force_login(administrator)

    response = client.post(
        reverse("server-list"), {"name": "nowhere"}, content_type="application/json"
    )

    assert response.status_code == 400
    assert "primary_ip" in response.json()


@pytest.mark.django_db
def test_a_viewer_cannot_register_a_server(client, viewer):
    client.force_login(viewer)

    response = client.post(
        reverse("server-list"),
        {"name": "web01", "primary_ip": "10.0.0.5"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert not Server.objects.exists()


@pytest.mark.django_db
def test_a_viewer_can_read_servers(client, viewer):
    Server.objects.create(name="web01", primary_ip="10.0.0.5")
    client.force_login(viewer)

    assert client.get(reverse("server-list")).status_code == 200


@pytest.mark.django_db
def test_the_api_exposes_the_inventory_representation(client, administrator):
    Server.objects.create(name="web01", primary_ip="10.0.0.5", ssh_port=2222)
    client.force_login(administrator)

    row = client.get(reverse("server-list")).json()["results"][0]

    assert row["inventory_host"]["ansible_host"] == "10.0.0.5"
    assert row["inventory_host"]["ansible_port"] == 2222


@pytest.mark.django_db
def test_registering_a_server_writes_an_audit_event(client, administrator):
    client.force_login(administrator)
    client.post(
        reverse("server-list"),
        {"name": "web01", "primary_ip": "10.0.0.5"},
        content_type="application/json",
    )

    event = AuditEvent.objects.filter(module="infrastructure").first()

    assert event is not None
    assert event.action == "CREATE"
    assert event.resource_type == "Server"
    assert event.username_snapshot == administrator.username


@pytest.mark.django_db
def test_deleting_a_server_is_audited(client, administrator):
    server = Server.objects.create(name="web01", primary_ip="10.0.0.5")
    client.force_login(administrator)

    client.delete(reverse("server-detail", args=[server.uuid]))

    event = AuditEvent.objects.filter(action="DELETE").first()
    assert event is not None
    assert event.resource_type == "Server"
    assert not Server.objects.filter(name="web01").exists()


@pytest.mark.django_db
def test_servers_can_be_filtered_by_client(client, administrator):
    acme = Client.objects.create(name="Acme")
    Server.objects.create(name="acme01", primary_ip="10.0.0.5", client=acme)
    Server.objects.create(name="other01", primary_ip="10.0.0.6")
    client.force_login(administrator)

    results = client.get(reverse("server-list"), {"client__slug": "acme"}).json()["results"]

    assert [r["name"] for r in results] == ["acme01"]


@pytest.mark.django_db
def test_servers_can_be_filtered_by_connection_method(client, administrator):
    Server.objects.create(name="lin01", primary_ip="10.0.0.5", connection_method="SSH")
    Server.objects.create(name="win01", primary_ip="10.0.0.6", connection_method="WINRM")
    client.force_login(administrator)

    results = client.get(reverse("server-list"), {"connection_method": "WINRM"}).json()["results"]

    assert [r["name"] for r in results] == ["win01"]


@pytest.mark.django_db
def test_a_server_can_be_attached_to_groups_by_slug(client, administrator):
    ServerGroup.objects.create(name="webservers")
    client.force_login(administrator)

    response = client.post(
        reverse("server-list"),
        json.dumps({"name": "web01", "primary_ip": "10.0.0.5", "groups": ["webservers"]}),
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    assert Server.objects.get(name="web01").groups.count() == 1


@pytest.mark.django_db
def test_environments_and_clients_have_endpoints(client, administrator):
    Environment.objects.create(name="Production")
    Client.objects.create(name="Acme")
    client.force_login(administrator)

    assert client.get(reverse("environment-list")).status_code == 200
    assert client.get(reverse("client-list")).status_code == 200
    assert client.get(reverse("servergroup-list")).status_code == 200


@pytest.mark.django_db
def test_winrm_servers_default_to_port_5986(client, administrator):
    client.force_login(administrator)

    client.post(
        reverse("server-list"),
        {"name": "win01", "primary_ip": "10.0.0.6", "connection_method": "WINRM"},
        content_type="application/json",
    )

    assert Server.objects.get(name="win01").ssh_port == 5986

"""Infrastructure models and the Ansible management screens."""

import pytest
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.urls import reverse

from authentication.models import Role, UserRole
from infrastructure.models import (
    Environment,
    OperatingSystem,
    Server,
    ServerGroup,
    ServerStatus,
)


@pytest.fixture
def seeded(db):
    call_command("seed_roles")


@pytest.fixture
def operator(user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="operator"))
    user.refresh_from_db()
    return user


@pytest.fixture
def production(db):
    return Environment.objects.create(name="Production")


# --- models ---------------------------------------------------------------


@pytest.mark.django_db
def test_environment_slug_is_derived_from_the_name():
    assert Environment.objects.create(name="Disaster Recovery").slug == "disaster-recovery"


@pytest.mark.django_db
def test_environment_names_are_unique(production):
    with pytest.raises(IntegrityError):
        Environment.objects.create(name="Production")


@pytest.mark.django_db
def test_environment_does_not_force_check_mode_by_default(production):
    assert production.require_check_mode is False


@pytest.mark.django_db
def test_server_group_slug_is_derived():
    assert ServerGroup.objects.create(name="Web Servers").slug == "web-servers"


@pytest.mark.django_db
def test_new_server_status_is_unknown_until_tested():
    server = Server.objects.create(name="web01")

    assert server.status == ServerStatus.UNKNOWN
    assert server.last_connection_test is None
    assert server.last_successful_connection is None


@pytest.mark.django_db
def test_server_defaults_match_ansible_conventions():
    server = Server.objects.create(name="web01")

    assert server.ssh_port == 22
    assert server.ansible_user == "ansible"
    assert server.operating_system == OperatingSystem.LINUX
    assert server.active is True


@pytest.mark.django_db
def test_ansible_host_prefers_the_explicit_ip():
    server = Server.objects.create(
        name="web01", hostname="web01.example.com", primary_ip="10.0.0.5"
    )

    assert server.ansible_host == "10.0.0.5"


@pytest.mark.django_db
def test_ansible_host_falls_back_to_dns_then_to_the_name():
    assert Server.objects.create(name="a", hostname="a.example.com").ansible_host == "a.example.com"
    assert Server.objects.create(name="b").ansible_host == "b"


@pytest.mark.django_db
def test_inventory_host_renders_standard_ansible_variables():
    server = Server.objects.create(
        name="web01", primary_ip="10.0.0.5", ssh_port=2222, ansible_user="deploy"
    )

    assert server.to_inventory_host() == {
        "ansible_host": "10.0.0.5",
        "ansible_port": 2222,
        "ansible_user": "deploy",
        "ansible_connection": "ssh",
    }


@pytest.mark.django_db
def test_the_transport_follows_the_connection_method_not_the_os():
    """A Windows host may still be reached over SSH, so OS must not decide."""
    windows_over_ssh = Server.objects.create(
        name="win-ssh", hostname="a", operating_system=OperatingSystem.WINDOWS
    )
    windows_over_winrm = Server.objects.create(
        name="win-winrm",
        hostname="b",
        operating_system=OperatingSystem.WINDOWS,
        connection_method="WINRM",
    )

    assert windows_over_ssh.to_inventory_host()["ansible_connection"] == "ssh"
    assert windows_over_winrm.to_inventory_host()["ansible_connection"] == "winrm"


@pytest.mark.django_db
def test_deleting_an_environment_in_use_is_refused(production):
    """A server must not be orphaned by removing its environment."""
    Server.objects.create(name="web01", environment=production)

    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        production.delete()


@pytest.mark.django_db
def test_group_membership_is_counted(production):
    group = ServerGroup.objects.create(name="webservers")
    Server.objects.create(name="web01").groups.add(group)
    Server.objects.create(name="web02").groups.add(group)

    assert group.member_count == 2


@pytest.mark.django_db
def test_server_names_are_unique():
    Server.objects.create(name="web01")

    with pytest.raises(IntegrityError):
        Server.objects.create(name="web01")


# --- screens --------------------------------------------------------------

SCREENS = ["manage:overview", "manage:servers", "manage:environments", "manage:groups"]


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_screens_require_authentication(client, route):
    response = client.get(reverse(route))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_operator_reaches_every_screen(client, operator, route):
    client.force_login(operator)

    assert client.get(reverse(route)).status_code == 200


@pytest.mark.django_db
def test_a_user_without_roles_is_denied_the_gated_screens(client, user, seeded):
    client.force_login(user)

    assert client.get(reverse("manage:servers")).status_code == 403
    assert client.get(reverse("manage:environments")).status_code == 403


@pytest.mark.django_db
def test_root_sends_a_signed_in_user_straight_to_management(client, operator):
    client.force_login(operator)

    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"] == reverse("manage:overview")


@pytest.mark.django_db
def test_root_sends_an_anonymous_visitor_to_sign_in(client):
    response = client.get("/")

    assert response.status_code == 302
    assert reverse("login") in response["Location"]


@pytest.mark.django_db
def test_server_detail_shows_the_inventory_variables(client, operator, production):
    server = Server.objects.create(name="web01", primary_ip="10.0.0.5", environment=production)
    client.force_login(operator)

    body = client.get(reverse("manage:server-detail", args=[server.uuid])).content.decode()

    assert "ansible_host" in body
    assert "10.0.0.5" in body


@pytest.mark.django_db
def test_servers_can_be_filtered_by_name(client, operator):
    Server.objects.create(name="web01")
    Server.objects.create(name="db01")
    client.force_login(operator)

    body = client.get(reverse("manage:servers"), {"q": "web"}).content.decode()

    assert "web01" in body
    assert "db01" not in body


@pytest.mark.django_db
def test_servers_can_be_filtered_by_environment(client, operator, production):
    staging = Environment.objects.create(name="Staging")
    Server.objects.create(name="prod01", environment=production)
    Server.objects.create(name="stage01", environment=staging)
    client.force_login(operator)

    body = client.get(reverse("manage:servers"), {"environment": "production"}).content.decode()

    assert "prod01" in body
    assert "stage01" not in body


@pytest.mark.django_db
def test_servers_can_be_filtered_by_status(client, operator):
    Server.objects.create(name="up01", status=ServerStatus.ONLINE)
    Server.objects.create(name="down01", status=ServerStatus.OFFLINE)
    client.force_login(operator)

    body = client.get(reverse("manage:servers"), {"status": "ONLINE"}).content.decode()

    assert "up01" in body
    assert "down01" not in body


@pytest.mark.django_db
@pytest.mark.parametrize("route", SCREENS)
def test_no_management_screen_links_to_django_admin(client, operator, route):
    """The product surface never routes into the operator backdoor."""
    client.force_login(operator)

    body = client.get(reverse(route)).content.decode()

    assert 'href="/admin/' not in body
    assert "Django Admin" not in body


@pytest.mark.django_db
def test_overview_counts_only_active_servers(client, operator):
    Server.objects.create(name="live01")
    Server.objects.create(name="retired01", active=False)
    client.force_login(operator)

    assert client.get(reverse("manage:overview")).context["counts"]["servers"] == 1


# --- web write flows ------------------------------------------------------


@pytest.fixture
def administrator(user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="administrator"))
    user.refresh_from_db()
    return user


@pytest.mark.django_db
def test_a_server_can_be_registered_from_the_web_form(client, administrator):
    client.force_login(administrator)

    response = client.post(
        reverse("manage:server-create"),
        {
            "name": "web09",
            "primary_ip": "10.0.0.9",
            "connection_method": "SSH",
            "ssh_port": 22,
            "ansible_user": "ansible",
            "operating_system": "LINUX",
            "active": "on",
        },
    )

    assert response.status_code == 302
    assert Server.objects.filter(name="web09").exists()


@pytest.mark.django_db
def test_the_web_form_refuses_an_unaddressable_server(client, administrator):
    client.force_login(administrator)

    response = client.post(
        reverse("manage:server-create"),
        {
            "name": "nowhere",
            "connection_method": "SSH",
            "ssh_port": 22,
            "ansible_user": "ansible",
            "operating_system": "LINUX",
        },
    )

    assert response.status_code == 200
    assert not Server.objects.filter(name="nowhere").exists()


@pytest.mark.django_db
def test_registering_from_the_web_records_the_creator_and_an_audit_event(client, administrator):
    from audit.models import AuditEvent

    client.force_login(administrator)
    client.post(
        reverse("manage:server-create"),
        {
            "name": "web10",
            "primary_ip": "10.0.0.10",
            "connection_method": "SSH",
            "ssh_port": 22,
            "ansible_user": "ansible",
            "operating_system": "LINUX",
        },
    )

    assert Server.objects.get(name="web10").created_by == administrator
    assert AuditEvent.objects.filter(module="infrastructure", action="CREATE").exists()


@pytest.mark.django_db
def test_a_viewer_cannot_open_the_registration_form(client, user, seeded):
    UserRole.objects.create(user=user, role=Role.objects.get(slug="viewer"))
    client.force_login(user)

    assert client.get(reverse("manage:server-create")).status_code == 403


@pytest.mark.django_db
def test_clients_and_credentials_screens_render(client, administrator):
    client.force_login(administrator)

    assert client.get(reverse("manage:clients")).status_code == 200
    assert client.get(reverse("manage:credentials")).status_code == 200


@pytest.mark.django_db
def test_a_credential_created_from_the_web_form_is_encrypted(client, administrator):
    from credentials.models import Credential

    client.force_login(administrator)
    client.post(
        reverse("manage:credential-create"),
        {"name": "web-key", "type": "SSH_PASSWORD", "username": "deploy", "secret": "s3cr3t"},
    )

    credential = Credential.objects.get(name="web-key")
    assert credential.encrypted_secret != "s3cr3t"
    assert credential.reveal_secret() == "s3cr3t"


@pytest.mark.django_db
def test_windows_servers_render_winrm_inventory_variables():
    server = Server.objects.create(name="win01", primary_ip="10.0.0.6", connection_method="WINRM")

    variables = server.to_inventory_host()

    assert variables["ansible_connection"] == "winrm"
    assert variables["ansible_port"] == 5986


@pytest.mark.django_db
def test_a_client_cannot_be_deleted_while_it_owns_servers():
    from django.db.models import ProtectedError

    from infrastructure.models import Client

    acme = Client.objects.create(name="Acme")
    Server.objects.create(name="acme01", primary_ip="10.0.0.5", client=acme)

    with pytest.raises(ProtectedError):
        acme.delete()

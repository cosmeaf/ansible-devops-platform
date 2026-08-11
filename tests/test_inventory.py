"""Generating a standard Ansible inventory from the registered servers."""

import pytest
import yaml
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.urls import reverse

from infrastructure.models import Client, ConnectionMethod, Environment, Server, ServerGroup
from inventory.builder import ansible_group_name, build, graph, render


@pytest.fixture
def fleet(db):
    production = Environment.objects.create(name="Production")
    staging = Environment.objects.create(name="Staging")
    avaliza = Client.objects.create(name="Avaliza")
    webservers = ServerGroup.objects.create(name="webservers")

    web01 = Server.objects.create(
        name="web01",
        primary_ip="198.51.100.10",
        ansible_user="deploy",
        ssh_port=2222,
        environment=production,
        client=avaliza,
    )
    web01.groups.add(webservers)

    Server.objects.create(
        name="db01",
        hostname="db01.internal.example",
        environment=staging,
    )
    return {"production": production, "avaliza": avaliza, "web01": web01}


def test_hosts_carry_their_connection_variables(fleet):
    hosts = build()["all"]["hosts"]

    assert hosts["web01"] == {
        "ansible_host": "198.51.100.10",
        "ansible_port": 2222,
        "ansible_user": "deploy",
        "ansible_connection": "ssh",
    }


def test_a_group_becomes_an_inventory_group(fleet):
    children = build()["all"]["children"]

    assert "web01" in children["webservers"]["hosts"]


def test_environments_and_clients_become_targetable_groups(fleet):
    children = build()["all"]["children"]

    assert "web01" in children["env_production"]["hosts"]
    assert "web01" in children["client_avaliza"]["hosts"]


def test_host_variables_are_written_once_and_membership_is_a_reference(fleet):
    """Repeating the address in every group is how inventories start to lie."""
    children = build()["all"]["children"]

    assert children["webservers"]["hosts"]["web01"] is None


def test_a_host_without_a_group_is_still_in_the_inventory(fleet):
    inventory = build()

    assert "db01" in inventory["all"]["hosts"]
    assert "db01" not in inventory["all"]["children"]["webservers"]["hosts"]


def test_filtering_by_environment(fleet):
    hosts = build(environment="production")["all"]["hosts"]

    assert set(hosts) == {"web01"}


def test_filtering_by_client(fleet):
    hosts = build(client="avaliza")["all"]["hosts"]

    assert set(hosts) == {"web01"}


def test_an_environment_instance_is_accepted_as_well_as_a_slug(fleet):
    hosts = build(environment=fleet["production"])["all"]["hosts"]

    assert set(hosts) == {"web01"}


def test_inactive_servers_are_left_out_unless_asked_for(fleet):
    Server.objects.create(name="retired01", primary_ip="198.51.100.99", active=False)

    assert "retired01" not in build()["all"]["hosts"]
    assert "retired01" in build(include_inactive=True)["all"]["hosts"]


def test_a_windows_host_declares_the_winrm_connection(fleet):
    Server.objects.create(
        name="win01",
        primary_ip="198.51.100.31",
        connection_method=ConnectionMethod.WINRM,
    )

    assert build()["all"]["hosts"]["win01"]["ansible_connection"] == "winrm"


def test_the_rendered_file_is_valid_yaml(fleet):
    assert yaml.safe_load(render()) == build()


def test_group_names_are_made_safe_for_ansible():
    assert ansible_group_name("web servers") == "web_servers"
    assert ansible_group_name("docker-hosts") == "docker_hosts"
    assert ansible_group_name("2fa") == "g_2fa"


def test_the_graph_reads_like_ansible_inventory(fleet):
    tree = graph(build())

    assert tree.startswith("@all:")
    assert "  |--@webservers:" in tree
    assert "  |  |--web01" in tree


def test_ungrouped_hosts_appear_under_ungrouped(fleet):
    Server.objects.create(name="loose01", primary_ip="198.51.100.77")

    assert "  |--@ungrouped:" in graph(build())


@pytest.mark.django_db
def test_the_command_writes_a_file(fleet, tmp_path):
    target = tmp_path / "inventories" / "production" / "hosts.yml"

    call_command("generate_inventory", environment="production", output=str(target))

    assert set(yaml.safe_load(target.read_text())["all"]["hosts"]) == {"web01"}


@pytest.mark.django_db
def test_the_command_rejects_an_unknown_environment(fleet):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("generate_inventory", environment="nowhere")


@pytest.fixture
def viewer(db):
    user = get_user_model().objects.create_user("viewer", password="fixture-password-not-a-secret-1")
    user.user_permissions.add(Permission.objects.get(codename="view_server"))
    return user


def test_the_page_needs_a_signed_in_user(client, fleet):
    response = client.get(reverse("inventory:preview"))

    assert response.status_code == 302


def test_the_page_shows_the_generated_inventory(client, fleet, viewer):
    client.force_login(viewer)

    response = client.get(reverse("inventory:preview"))

    assert response.status_code == 200
    assert "web01" in response.content.decode()


def test_the_inventory_can_be_downloaded(client, fleet, viewer):
    client.force_login(viewer)

    response = client.get(reverse("inventory:preview"), {"download": "1"})

    assert response["Content-Disposition"] == 'attachment; filename="hosts.yml"'
    assert yaml.safe_load(response.content.decode())["all"]["hosts"]["web01"]


def test_a_filtered_download_is_named_after_its_scope(client, fleet, viewer):
    client.force_login(viewer)

    response = client.get(
        reverse("inventory:preview"), {"download": "1", "environment": "production"}
    )

    assert response["Content-Disposition"] == 'attachment; filename="production-hosts.yml"'

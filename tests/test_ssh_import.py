"""Importing an existing ssh_config as inventory."""

import pytest
from django.core.management import call_command

from infrastructure.models import Server
from infrastructure.ssh_config import importable, parse

SAMPLE = """
# a comment
Host *
    ServerAliveInterval 60

Host web01 web01.example.com
    HostName 198.51.100.10
    User deploy
    Port 2222
    IdentityFile ~/.ssh/web_key

Host db01
    HostName db01.internal.example
    User root

Host legacy
    HostName 198.51.100.99
    User admin
    ProxyJump bastion.example.com

Host github.com-work
    HostName github.com
    User git

Host no-address
    User nobody
"""


def test_host_blocks_are_parsed():
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert "web01" in hosts
    assert hosts["web01"].hostname == "198.51.100.10"
    assert hosts["web01"].user == "deploy"
    assert hosts["web01"].port == 2222
    assert hosts["web01"].identity_file == "~/.ssh/web_key"


def test_aliases_are_kept():
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert hosts["web01"].aliases == ["web01", "web01.example.com"]


def test_comments_and_unknown_directives_are_ignored():
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert hosts["db01"].port is None
    assert hosts["db01"].user == "root"


def test_a_wildcard_block_is_not_importable():
    assert not any(h.is_wildcard for h in importable(parse(SAMPLE)))


def test_git_forges_are_skipped():
    names = [h.name for h in importable(parse(SAMPLE), skip_patterns=("github.com",))]

    assert "github.com-work" not in names


def test_a_host_without_an_address_still_uses_its_name():
    """`Host foo` with no HostName is valid ssh_config; the name is the address."""
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert hosts["no-address"].reaches_a_host is True


def test_a_jump_host_is_detected():
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert hosts["legacy"].needs_a_jump is True
    assert hosts["legacy"].proxy_jump == "bastion.example.com"
    assert hosts["web01"].needs_a_jump is False


def test_directives_may_use_equals_separators():
    hosts = {h.name: h for h in parse("Host a\n  HostName=198.51.100.1\n  Port=2200\n")}

    assert hosts["a"].hostname == "198.51.100.1"
    assert hosts["a"].port == 2200


def test_a_non_numeric_port_is_ignored_rather_than_crashing():
    hosts = {h.name: h for h in parse("Host a\n  HostName 198.51.100.1\n  Port banana\n")}

    assert hosts["a"].port is None


@pytest.mark.django_db
def test_import_registers_servers(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command("import_ssh_config", path=str(config))

    assert Server.objects.filter(name="web01").exists()
    assert Server.objects.get(name="web01").ssh_port == 2222
    assert Server.objects.get(name="web01").ansible_user == "deploy"


@pytest.mark.django_db
def test_import_separates_ip_addresses_from_dns_names(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command("import_ssh_config", path=str(config))

    by_ip = Server.objects.get(name="web01")
    by_name = Server.objects.get(name="db01")

    assert by_ip.primary_ip == "198.51.100.10"
    assert by_ip.hostname == ""
    assert by_name.hostname == "db01.internal.example"
    assert by_name.primary_ip is None


@pytest.mark.django_db
def test_import_is_idempotent(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command("import_ssh_config", path=str(config))
    before = Server.objects.count()
    call_command("import_ssh_config", path=str(config))

    assert Server.objects.count() == before


@pytest.mark.django_db
def test_dry_run_writes_nothing(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command("import_ssh_config", path=str(config), dry_run=True)

    assert Server.objects.count() == 0


@pytest.mark.django_db
def test_import_can_assign_a_client_environment_and_groups(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command(
        "import_ssh_config",
        path=str(config),
        client="Acme",
        environment="Production",
        group=["imported"],
    )

    server = Server.objects.get(name="web01")
    assert server.client.name == "Acme"
    assert server.environment.name == "Production"
    assert server.groups.filter(name="imported").exists()


@pytest.mark.django_db
def test_a_jump_host_is_recorded_in_the_description(tmp_path):
    config = tmp_path / "config"
    config.write_text(SAMPLE)

    call_command("import_ssh_config", path=str(config))

    assert "bastion.example.com" in Server.objects.get(name="legacy").description


@pytest.mark.django_db
def test_a_missing_config_is_an_error(tmp_path):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("import_ssh_config", path=str(tmp_path / "nope"))

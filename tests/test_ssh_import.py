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

    description = Server.objects.get(name="legacy").description

    assert description == "Imported from config; reachable via bastion.example.com"


@pytest.mark.django_db
def test_a_missing_config_is_an_error(tmp_path):
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("import_ssh_config", path=str(tmp_path / "nope"))


BANNERED = """
################################
# AVALIZA
################################
# IdentitiesOnly keeps the agent from offering the other keys first.
Host avaliza-srv-01
    HostName 198.51.100.20
    User root

Host avaliza.app
    HostName 198.51.100.21
    User deploy

################################
# S2DIGITAL
################################
Host monitor
    HostName 198.51.100.30
    User ops

#### VELOMA
Host veloma-srv-01
    HostName 198.51.100.40
    User root
"""


def test_banner_comments_become_sections():
    hosts = {h.name: h for h in parse(BANNERED)}

    assert hosts["avaliza-srv-01"].section == "AVALIZA"
    assert hosts["avaliza.app"].section == "AVALIZA"
    assert hosts["monitor"].section == "S2DIGITAL"


def test_a_comment_explaining_a_directive_is_not_a_section():
    """Only banners are sections; prose under one must not replace it."""
    hosts = {h.name: h for h in parse(BANNERED)}

    assert hosts["avaliza-srv-01"].section == "AVALIZA"


def test_a_title_written_on_the_rule_itself_is_a_section():
    hosts = {h.name: h for h in parse(BANNERED)}

    assert hosts["veloma-srv-01"].section == "VELOMA"


def test_a_host_before_any_banner_has_no_section():
    hosts = {h.name: h for h in parse(SAMPLE)}

    assert hosts["web01"].section == ""


def test_shouted_sections_read_as_client_names():
    hosts = {h.name: h for h in parse(BANNERED)}

    assert hosts["monitor"].client_name == "S2Digital"
    assert hosts["avaliza-srv-01"].client_name == "Avaliza"


@pytest.mark.django_db
def test_each_section_becomes_a_client(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)

    call_command("import_ssh_config", path=str(config))

    assert Server.objects.get(name="avaliza-srv-01").client.name == "Avaliza"
    assert Server.objects.get(name="avaliza.app").client.name == "Avaliza"
    assert Server.objects.get(name="monitor").client.name == "S2Digital"


@pytest.mark.django_db
def test_an_explicit_client_overrides_the_sections(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)

    call_command("import_ssh_config", path=str(config), client="Acme")

    assert {s.client.name for s in Server.objects.all()} == {"Acme"}


@pytest.mark.django_db
def test_section_clients_can_be_turned_off(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)

    call_command("import_ssh_config", path=str(config), section_clients=False)

    assert Server.objects.get(name="monitor").client is None


@pytest.mark.django_db
def test_update_existing_backfills_a_server_imported_without_a_client(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)
    call_command("import_ssh_config", path=str(config), section_clients=False)

    call_command("import_ssh_config", path=str(config), update_existing=True)

    assert Server.objects.get(name="monitor").client.name == "S2Digital"
    assert Server.objects.count() == 4


@pytest.mark.django_db
def test_update_existing_keeps_a_client_someone_already_chose(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)
    call_command("import_ssh_config", path=str(config), client="Acme")

    call_command("import_ssh_config", path=str(config), update_existing=True)

    assert Server.objects.get(name="monitor").client.name == "Acme"


@pytest.mark.django_db
def test_update_existing_adds_missing_groups_and_environment(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)
    call_command("import_ssh_config", path=str(config))

    call_command(
        "import_ssh_config",
        path=str(config),
        update_existing=True,
        environment="Production",
        group=["imported"],
    )

    server = Server.objects.get(name="monitor")
    assert server.environment.name == "Production"
    assert server.groups.filter(name="imported").exists()


@pytest.mark.django_db
def test_a_dry_run_update_writes_nothing(tmp_path):
    config = tmp_path / "config"
    config.write_text(BANNERED)
    call_command("import_ssh_config", path=str(config), section_clients=False)

    call_command("import_ssh_config", path=str(config), update_existing=True, dry_run=True)

    assert Server.objects.get(name="monitor").client is None

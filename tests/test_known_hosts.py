"""Deciding which host keys the platform trusts."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from automation import known_hosts
from automation.known_hosts import HostKey, ScanFailed, forget, is_trusted, trust
from infrastructure.models import Server

ED25519 = "198.51.100.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample"
RSA = "198.51.100.10 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQExample"


@pytest.fixture
def workspace(tmp_path, settings):
    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    return settings.ANSIBLE_WORKSPACE


def key(line=ED25519, host="198.51.100.10", port=22, key_type="ED25519"):
    return HostKey(host=host, port=port, key_type=key_type, fingerprint="SHA256:abc123", line=line)


# --- the file ---------------------------------------------------------------


def test_the_known_hosts_file_lives_in_the_workspace(workspace):
    path = known_hosts.known_hosts_path()

    assert path == workspace / "known_hosts"
    assert path.is_file()


def test_a_host_is_not_trusted_until_it_is_accepted(workspace):
    assert is_trusted("198.51.100.10") is False

    trust([key()])

    assert is_trusted("198.51.100.10") is True


def test_trusting_is_idempotent(workspace):
    assert trust([key()]) == 1
    assert trust([key()]) == 0
    assert known_hosts.known_hosts_path().read_text().count("ssh-ed25519") == 1


def test_every_key_a_host_offers_is_recorded(workspace):
    added = trust([key(), key(line=RSA, key_type="RSA")])

    assert added == 2
    assert is_trusted("198.51.100.10") is True


def test_a_non_standard_port_is_tracked_separately(workspace):
    trust([key(line="[198.51.100.10]:2222 ssh-ed25519 AAAAC3Example", port=2222)])

    assert is_trusted("198.51.100.10", 2222) is True
    assert is_trusted("198.51.100.10", 22) is False


def test_forgetting_a_host_removes_its_keys(workspace):
    trust([key(), key(line=RSA, key_type="RSA")])

    assert forget("198.51.100.10") == 2
    assert is_trusted("198.51.100.10") is False


def test_forgetting_leaves_other_hosts_alone(workspace):
    trust([key()])
    trust([key(line="198.51.100.99 ssh-ed25519 AAAAC3Other", host="198.51.100.99")])

    forget("198.51.100.10")

    assert is_trusted("198.51.100.99") is True


# --- scanning ---------------------------------------------------------------


def test_a_host_that_offers_nothing_is_an_error(workspace):
    with patch("automation.known_hosts.subprocess.run") as run:
        run.return_value.stdout = ""
        run.return_value.returncode = 0

        with pytest.raises(ScanFailed, match="offered no host key"):
            known_hosts.scan("198.51.100.10")


def test_an_unreachable_host_is_an_error_rather_than_a_crash(workspace):
    with patch("automation.known_hosts.subprocess.run", side_effect=OSError("no route")):
        with pytest.raises(ScanFailed, match="Could not reach"):
            known_hosts.scan("198.51.100.10")


def test_comment_lines_from_keyscan_are_ignored(workspace):
    outputs = [
        type("R", (), {"stdout": f"# 198.51.100.10:22 SSH-2.0\n{ED25519}\n", "returncode": 0})(),
        type("R", (), {"stdout": "256 SHA256:abc123 host (ED25519)\n", "returncode": 0})(),
    ]
    with patch("automation.known_hosts.subprocess.run", side_effect=outputs):
        keys = known_hosts.scan("198.51.100.10")

    assert len(keys) == 1
    assert keys[0].fingerprint == "SHA256:abc123"
    assert keys[0].key_type == "ED25519"


# --- the runner refuses to hang ---------------------------------------------


def test_the_runner_never_lets_ssh_wait_for_an_answer(workspace):
    """A prompt in a worker is a timeout with extra steps."""
    from automation import runner

    captured = {}

    class FakeRun:
        status, rc, stats, stdout = "successful", 0, {}, None

    def fake_run(**kwargs):
        captured.update(kwargs)
        return FakeRun()

    class FakeServer:
        name = "web01"
        credential = None

        def to_inventory_host(self):
            return {"ansible_host": "198.51.100.10"}

    with patch("automation.runner.ansible_runner.run", side_effect=fake_run):
        runner.run_module([FakeServer()], module="ping")

    args = captured["envvars"]["ANSIBLE_SSH_ARGS"]
    assert "-o BatchMode=yes" in args
    assert "-o StrictHostKeyChecking=yes" in args
    assert str(known_hosts.known_hosts_path()) in args
    assert captured["envvars"]["ANSIBLE_HOST_KEY_CHECKING"] == "True"


# --- the web surface --------------------------------------------------------


@pytest.fixture
def operator(db):
    user = get_user_model().objects.create_user(
        "trust-op", password="fixture-password-not-a-secret-1"
    )
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="jobs"),
        Permission.objects.get(codename="change_server"),
        Permission.objects.get(codename="view_server"),
    )
    return user


@pytest.fixture
def server(db):
    return Server.objects.create(name="web01", primary_ip="198.51.100.10")


@pytest.mark.django_db
def test_the_fingerprint_is_shown_before_anything_is_trusted(client, operator, server, workspace):
    client.force_login(operator)

    with patch("jobs.views.scan", return_value=[key()]):
        response = client.get(reverse("jobs:server-trust", args=[server.uuid]))

    assert response.status_code == 200
    assert "SHA256:abc123" in response.content.decode()
    assert is_trusted("198.51.100.10") is False


@pytest.mark.django_db
def test_accepting_records_the_key(client, operator, server, workspace):
    client.force_login(operator)

    with patch("jobs.views.scan", return_value=[key()]):
        client.post(reverse("jobs:server-trust", args=[server.uuid]))

    assert is_trusted("198.51.100.10") is True


@pytest.mark.django_db
def test_accepting_a_key_is_audited(client, operator, server, workspace):
    from audit.models import AuditEvent

    client.force_login(operator)

    with patch("jobs.views.scan", return_value=[key()]):
        client.post(reverse("jobs:server-trust", args=[server.uuid]))

    event = AuditEvent.objects.filter(resource_type="Server").latest("created_at")
    assert event.new_value["trusted_host_key"] == "198.51.100.10"
    assert "SHA256:abc123" in event.new_value["fingerprints"][0]


@pytest.mark.django_db
def test_a_connection_test_is_refused_until_the_key_is_accepted(
    client, operator, server, workspace
):
    """Otherwise the run just times out and nobody knows why."""
    from jobs.models import Job

    client.force_login(operator)

    with patch("jobs.views.check_connection.delay") as queued:
        response = client.post(reverse("jobs:server-test", args=[server.uuid]))

    assert response.status_code == 302
    assert reverse("jobs:server-trust", args=[server.uuid]) in response.url
    assert not Job.objects.exists()
    queued.assert_not_called()


@pytest.mark.django_db
def test_a_connection_test_proceeds_once_the_key_is_accepted(client, operator, server, workspace):
    from jobs.models import Job

    trust([key()])
    client.force_login(operator)

    with patch("jobs.views.check_connection.delay") as queued:
        client.post(reverse("jobs:server-test", args=[server.uuid]))

    assert Job.objects.count() == 1
    queued.assert_called_once()


@pytest.mark.django_db
def test_forgetting_a_key_from_the_web(client, operator, server, workspace):
    trust([key()])
    client.force_login(operator)

    client.post(reverse("jobs:server-forget", args=[server.uuid]))

    assert is_trusted("198.51.100.10") is False


@pytest.mark.django_db
def test_the_server_page_warns_when_no_key_is_trusted(client, operator, server, workspace):
    client.force_login(operator)

    body = client.get(reverse("manage:server-detail", args=[server.uuid])).content.decode()

    assert "No host key has been accepted" in body
    assert reverse("jobs:server-trust", args=[server.uuid]) in body


@pytest.mark.django_db
def test_a_host_that_cannot_be_scanned_reports_why(client, operator, server, workspace):
    client.force_login(operator)

    with patch("jobs.views.scan", side_effect=ScanFailed("offered no host key")):
        response = client.get(reverse("jobs:server-trust", args=[server.uuid]), follow=True)

    assert "offered no host key" in response.content.decode()

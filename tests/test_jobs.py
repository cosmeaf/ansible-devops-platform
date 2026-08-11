"""Running Ansible, and recording what it did."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from automation import runner
from automation.runner import HostResult, RunResult, parse_extra_vars
from credentials.models import Credential, CredentialType
from infrastructure.models import (
    ConnectionMethod,
    Environment,
    Server,
    ServerGroup,
    ServerStatus,
)
from jobs.models import Job, JobKind, JobStatus
from jobs.tasks import check_connection, run_job


class LocalServer:
    """A host Ansible reaches without a network, for the real run below."""

    name = "localhost"
    credential = None
    connection_method = ConnectionMethod.SSH

    def to_inventory_host(self):
        return {"ansible_connection": "local"}


# --- the runner, against real Ansible ---------------------------------------


@pytest.mark.slow
def test_ansible_actually_runs():
    """Not a mock. If this fails, nothing else in this file means anything."""
    result = runner.run_module([LocalServer()], module="ping", timeout=60)

    assert result.successful
    assert result.rc == 0
    assert result.hosts["localhost"].ok == 1
    assert result.summary() == "ok=1 changed=0 failed=0 unreachable=0"


@pytest.mark.slow
def test_a_failing_module_is_reported_as_failed():
    result = runner.run_module(
        [LocalServer()], module="fail", module_args="msg='on purpose'", timeout=60
    )

    assert not result.successful
    assert result.hosts["localhost"].failures == 1


@pytest.mark.slow
def test_a_run_leaves_no_temporary_directory_behind(tmp_path):
    import tempfile
    from pathlib import Path

    before = {p.name for p in Path(tempfile.gettempdir()).glob("ansible-run-*")}
    runner.run_module([LocalServer()], module="ping", timeout=60)
    after = {p.name for p in Path(tempfile.gettempdir()).glob("ansible-run-*")}

    assert after == before


# --- credentials become connection variables --------------------------------


@pytest.mark.django_db
def test_a_private_key_is_written_with_owner_only_permissions(tmp_path):
    import os
    import stat

    credential = Credential.objects.create(
        name="deploy", type=CredentialType.SSH_PRIVATE_KEY, username="root"
    )
    credential.set_secret("-----BEGIN KEY-----\nnot-a-real-key\n-----END KEY-----")
    credential.save()

    variables = runner._connection_vars(credential, directory=tmp_path)

    key = tmp_path / "id_key"
    assert variables["ansible_ssh_private_key_file"] == str(key)
    assert variables["ansible_user"] == "root"
    assert stat.S_IMODE(os.stat(key).st_mode) == 0o600


@pytest.mark.django_db
def test_a_password_credential_becomes_an_ansible_variable(tmp_path):
    credential = Credential.objects.create(
        name="pw", type=CredentialType.SSH_PASSWORD, username="ops"
    )
    credential.set_secret("hunter2")
    credential.save()

    variables = runner._connection_vars(credential, directory=tmp_path)

    assert variables["ansible_password"] == "hunter2"
    assert not (tmp_path / "id_key").exists()


@pytest.mark.django_db
def test_the_generated_inventory_carries_the_credential(tmp_path):
    credential = Credential.objects.create(
        name="pw", type=CredentialType.SSH_PASSWORD, username="ops"
    )
    credential.set_secret("hunter2")
    credential.save()
    server = Server.objects.create(name="web01", primary_ip="198.51.100.10")

    inventory = runner._inventory_for([server], credential=credential, directory=tmp_path)

    assert "ansible_password: hunter2" in inventory
    assert "ansible_user: ops" in inventory


# --- extra vars -------------------------------------------------------------


def test_extra_vars_are_parsed_as_yaml():
    assert parse_extra_vars("app_version: 4.12.0\ncount: 2") == {
        "app_version": "4.12.0",
        "count": 2,
    }


def test_empty_extra_vars_are_an_empty_mapping():
    assert parse_extra_vars("   ") == {}


def test_extra_vars_that_are_not_a_mapping_are_refused():
    with pytest.raises(ValueError, match="mapping"):
        parse_extra_vars("- one\n- two")


def test_extra_vars_that_are_not_yaml_are_refused():
    with pytest.raises(ValueError, match="not valid YAML"):
        parse_extra_vars("key: [unclosed")


# --- the job lifecycle ------------------------------------------------------


@pytest.fixture
def server(db):
    return Server.objects.create(name="web01", primary_ip="198.51.100.10")


def _succeeded():
    return RunResult(
        status=runner.SUCCESSFUL,
        rc=0,
        stdout="PLAY RECAP",
        hosts={"web01": HostResult(host="web01", ok=3, changed=1)},
    )


def _unreachable():
    return RunResult(
        status=runner.FAILED,
        rc=4,
        stdout="UNREACHABLE!",
        hosts={"web01": HostResult(host="web01", unreachable=1)},
    )


def _answered_but_failed():
    return RunResult(
        status=runner.FAILED,
        rc=2,
        stdout="FAILED!",
        hosts={"web01": HostResult(host="web01", failures=1)},
    )


@pytest.mark.django_db
def test_a_successful_job_records_its_recap(server):
    job = Job.objects.create(playbook="update.yml", status=JobStatus.QUEUED)
    job.servers.set([server])

    with patch("automation.runner.run_playbook", return_value=_succeeded()):
        run_job(str(job.uuid))

    job.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.exit_code == 0
    assert job.recap["web01"]["changed"] == 1
    assert job.started_at and job.finished_at


@pytest.mark.django_db
def test_a_failing_job_is_recorded_rather_than_lost(server):
    job = Job.objects.create(playbook="update.yml", status=JobStatus.QUEUED)
    job.servers.set([server])

    with patch("automation.runner.run_playbook", side_effect=RuntimeError("no such playbook")):
        run_job(str(job.uuid))

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "no such playbook" in job.error


@pytest.mark.django_db
def test_a_job_with_no_servers_says_so(db):
    job = Job.objects.create(playbook="update.yml", status=JobStatus.QUEUED)

    run_job(str(job.uuid))

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "nothing to run against" in job.error


@pytest.mark.django_db
def test_a_job_that_already_finished_is_not_run_again(server):
    job = Job.objects.create(playbook="update.yml", status=JobStatus.SUCCESS)
    job.servers.set([server])

    with patch("automation.runner.run_playbook") as run:
        run_job(str(job.uuid))

    run.assert_not_called()


@pytest.mark.django_db
def test_a_missing_job_does_not_raise():
    import uuid as uuid_module

    assert run_job(str(uuid_module.uuid4())) == "missing"


# --- connection test --------------------------------------------------------


@pytest.mark.django_db
def test_a_reachable_host_is_marked_online(server):
    job = Job.objects.create(kind=JobKind.CONNECTION_TEST, status=JobStatus.QUEUED)
    job.servers.set([server])

    with patch("automation.runner.run_module", return_value=_succeeded()):
        check_connection(str(job.uuid))

    server.refresh_from_db()
    assert server.status == ServerStatus.ONLINE
    assert server.last_successful_connection is not None


@pytest.mark.django_db
def test_an_unreachable_host_is_marked_offline(server):
    job = Job.objects.create(kind=JobKind.CONNECTION_TEST, status=JobStatus.QUEUED)
    job.servers.set([server])

    with patch("automation.runner.run_module", return_value=_unreachable()):
        check_connection(str(job.uuid))

    server.refresh_from_db()
    assert server.status == ServerStatus.OFFLINE
    assert server.last_successful_connection is None
    assert server.last_connection_test is not None


@pytest.mark.django_db
def test_a_host_that_answered_but_failed_is_not_called_online(server):
    """Reachable is not usable. Marking it ONLINE would be a lie."""
    job = Job.objects.create(kind=JobKind.CONNECTION_TEST, status=JobStatus.QUEUED)
    job.servers.set([server])

    with patch("automation.runner.run_module", return_value=_answered_but_failed()):
        check_connection(str(job.uuid))

    server.refresh_from_db()
    assert server.status == ServerStatus.ERROR
    assert server.last_successful_connection is None


@pytest.mark.django_db
def test_a_host_missing_from_the_recap_is_an_error(server):
    job = Job.objects.create(kind=JobKind.CONNECTION_TEST, status=JobStatus.QUEUED)
    job.servers.set([server])
    empty = RunResult(status=runner.FAILED, rc=1, stdout="", hosts={})

    with patch("automation.runner.run_module", return_value=empty):
        check_connection(str(job.uuid))

    server.refresh_from_db()
    assert server.status == ServerStatus.ERROR


@pytest.mark.django_db
def test_a_windows_host_is_tested_with_win_ping(db):
    windows = Server.objects.create(
        name="win01", primary_ip="198.51.100.31", connection_method=ConnectionMethod.WINRM
    )
    job = Job.objects.create(kind=JobKind.CONNECTION_TEST, status=JobStatus.QUEUED)
    job.servers.set([windows])

    with patch("automation.runner.run_module", return_value=_succeeded()) as run:
        check_connection(str(job.uuid))

    assert run.call_args.kwargs["module"] == "ansible.windows.win_ping"


# --- the web surface --------------------------------------------------------


@pytest.fixture
def operator(db):
    user = get_user_model().objects.create_user("operator", password="jobs-pass-1")
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="jobs"),
        Permission.objects.get(codename="change_server"),
        Permission.objects.get(codename="view_server"),
    )
    return user


def test_the_job_list_needs_a_signed_in_user(client, db):
    assert client.get(reverse("jobs:list")).status_code == 302


def test_the_job_list_renders(client, operator):
    client.force_login(operator)

    assert client.get(reverse("jobs:list")).status_code == 200


@pytest.mark.django_db
def test_running_a_playbook_queues_a_job(client, operator, server, tmp_path, settings):
    from automation.workspace import write_playbook

    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    write_playbook("update.yml", "---\n- name: x\n  hosts: all\n  tasks: []\n")
    client.force_login(operator)

    with patch("jobs.views.run_job.delay") as queued:
        response = client.post(
            reverse("jobs:run"),
            {"playbook": "update.yml", "check_mode": "on", "limit": "", "tags": ""},
        )

    assert response.status_code == 302
    job = Job.objects.get()
    assert job.status == JobStatus.QUEUED
    assert job.check_mode is True
    assert job.requested_by == operator
    assert list(job.servers.all()) == [server]
    queued.assert_called_once_with(str(job.uuid))


@pytest.mark.django_db
def test_a_run_that_would_target_nothing_is_refused(client, operator, tmp_path, settings):
    """An empty selection is a filter mistake, not a job worth queueing."""
    from automation.workspace import write_playbook

    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    write_playbook("update.yml", "---\n- name: x\n  hosts: all\n  tasks: []\n")
    environment = Environment.objects.create(name="Empty")
    client.force_login(operator)

    with patch("jobs.views.run_job.delay") as queued:
        response = client.post(
            reverse("jobs:run"),
            {"playbook": "update.yml", "environment": environment.pk, "check_mode": "on"},
        )

    assert response.status_code == 200
    assert not Job.objects.exists()
    queued.assert_not_called()


@pytest.mark.django_db
def test_a_group_narrows_the_servers_a_job_targets(client, operator, server, tmp_path, settings):
    from automation.workspace import write_playbook

    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    write_playbook("update.yml", "---\n- name: x\n  hosts: all\n  tasks: []\n")
    group = ServerGroup.objects.create(name="webservers")
    server.groups.add(group)
    Server.objects.create(name="db01", primary_ip="198.51.100.20")
    client.force_login(operator)

    with patch("jobs.views.run_job.delay"):
        client.post(
            reverse("jobs:run"),
            {"playbook": "update.yml", "group": group.pk, "check_mode": "on"},
        )

    assert list(Job.objects.get().servers.all()) == [server]


@pytest.mark.django_db
def test_testing_a_connection_queues_a_job(client, operator, server):
    client.force_login(operator)

    with patch("jobs.views.check_connection.delay") as queued:
        response = client.post(reverse("jobs:server-test", args=[server.uuid]))

    assert response.status_code == 302
    job = Job.objects.get()
    assert job.kind == JobKind.CONNECTION_TEST
    assert list(job.servers.all()) == [server]
    queued.assert_called_once_with(str(job.uuid))


@pytest.mark.django_db
def test_a_connection_test_cannot_be_triggered_by_a_get(client, operator, server):
    """A state-changing action behind GET is one a link preview can fire."""
    client.force_login(operator)

    assert client.get(reverse("jobs:server-test", args=[server.uuid])).status_code == 405


@pytest.mark.django_db
def test_the_status_endpoint_reports_progress(client, operator, server):
    job = Job.objects.create(playbook="update.yml", status=JobStatus.RUNNING)
    client.force_login(operator)

    payload = client.get(reverse("jobs:status", args=[job.uuid])).json()

    assert payload["status"] == "RUNNING"
    assert payload["finished"] is False


@pytest.mark.django_db
def test_launching_a_job_is_audited(client, operator, server, tmp_path, settings):
    from audit.models import AuditEvent
    from automation.workspace import write_playbook

    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    write_playbook("update.yml", "---\n- name: x\n  hosts: all\n  tasks: []\n")
    client.force_login(operator)

    with patch("jobs.views.run_job.delay"):
        client.post(reverse("jobs:run"), {"playbook": "update.yml", "check_mode": "on"})

    event = AuditEvent.objects.filter(module="jobs").latest("created_at")
    assert event.action == "CHECK"
    assert event.username_snapshot == "operator"

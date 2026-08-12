"""Reading the audit trail: who did what, and when."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from audit.models import AuditAction, AuditEvent, AuditResult
from audit.views import history_for
from infrastructure.models import Server, ServerGroup


@pytest.fixture
def auditor(db):
    user = get_user_model().objects.create_user("auditor", password="fixture-password-not-a-secret-1")
    user.user_permissions.add(Permission.objects.get(codename="view_auditevent"))
    return user


@pytest.fixture
def manager(db):
    user = get_user_model().objects.create_user("manager2", password="fixture-password-not-a-secret-1")
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="infrastructure"))
    return user


def _event(**kwargs):
    defaults = {
        "username_snapshot": "someone",
        "module": "infrastructure",
        "resource_type": "Server",
        "resource_id": "web01",
        "action": AuditAction.DELETE,
        "result": AuditResult.SUCCESS,
        "source_ip": "198.51.100.5",
    }
    return AuditEvent.objects.create(**{**defaults, **kwargs})


# --- the trail is reachable at all ------------------------------------------


def test_the_trail_needs_a_signed_in_user(client, db):
    assert client.get(reverse("audit:trail")).status_code == 302


def test_a_user_without_the_permission_cannot_read_it(client, db):
    nobody = get_user_model().objects.create_user("nosy", password="fixture-password-not-a-secret-1")
    client.force_login(nobody)

    assert client.get(reverse("audit:trail")).status_code == 403


def test_the_trail_shows_who_did_what(client, auditor):
    _event()
    client.force_login(auditor)

    body = client.get(reverse("audit:trail")).content.decode()

    assert "someone" in body
    assert "web01" in body
    assert "Delete" in body


# --- filtering --------------------------------------------------------------


def test_filtering_by_action(client, auditor):
    _event(action=AuditAction.DELETE, resource_id="deleted-one")
    _event(action=AuditAction.CREATE, resource_id="created-one")
    client.force_login(auditor)

    body = client.get(reverse("audit:trail"), {"action": "DELETE"}).content.decode()

    assert "deleted-one" in body
    assert "created-one" not in body


def test_filtering_by_who(client, auditor):
    _event(username_snapshot="alice", resource_id="alice-did-this")
    _event(username_snapshot="bob", resource_id="bob-did-this")
    client.force_login(auditor)

    body = client.get(reverse("audit:trail"), {"username": "alice"}).content.decode()

    assert "alice-did-this" in body
    assert "bob-did-this" not in body


def test_filtering_by_module(client, auditor):
    _event(module="jobs", resource_id="a-job")
    _event(module="automation", resource_id="a-file")
    client.force_login(auditor)

    body = client.get(reverse("audit:trail"), {"module": "jobs"}).content.decode()

    assert "a-job" in body
    assert "a-file" not in body


def test_searching_by_resource(client, auditor):
    _event(resource_id="playbooks/linux/update.yml")
    _event(resource_id="roles/nginx")
    client.force_login(auditor)

    body = client.get(reverse("audit:trail"), {"resource": "nginx"}).content.decode()

    assert "roles/nginx" in body
    assert "update.yml" not in body


# --- one event in full ------------------------------------------------------


def test_an_event_shows_what_was_there_before(client, auditor):
    event = _event(previous_value={"name": "web01", "type": "Server"})
    client.force_login(auditor)

    body = client.get(reverse("audit:event", args=[event.uuid])).content.decode()

    assert "web01" in body
    assert "Before" in body


def test_an_event_links_to_everything_else_about_that_resource(client, auditor):
    _event(action=AuditAction.CREATE, resource_id="web01")
    event = _event(action=AuditAction.DELETE, resource_id="web01")
    client.force_login(auditor)

    body = client.get(reverse("audit:event", args=[event.uuid])).content.decode()

    assert "Everything else recorded" in body


# --- the trail is written by the actions it describes ------------------------


def test_deleting_a_group_is_traceable_to_the_person(client, manager):
    group = ServerGroup.objects.create(name="webservers")
    client.force_login(manager)

    client.post(reverse("manage:group-delete", args=[group.uuid]))

    event = AuditEvent.objects.filter(action=AuditAction.DELETE).latest("created_at")
    assert event.username_snapshot == "manager2"
    assert event.previous_value == {"name": "webservers", "type": "ServerGroup"}
    assert event.new_value is None


def test_a_deletion_records_what_was_there_not_what_replaced_it(client, manager):
    """There is no 'after' for a deletion, so previous_value is where it goes."""
    server = Server.objects.create(name="web01", primary_ip="198.51.100.10")
    client.force_login(manager)

    client.post(reverse("manage:server-delete", args=[server.uuid]))

    event = AuditEvent.objects.filter(resource_type="Server").latest("created_at")
    assert event.previous_value["name"] == "web01"


def test_the_trail_survives_the_account_that_made_it(client, manager):
    group = ServerGroup.objects.create(name="webservers")
    client.force_login(manager)
    client.post(reverse("manage:group-delete", args=[group.uuid]))

    manager.delete()

    event = AuditEvent.objects.filter(action=AuditAction.DELETE).latest("created_at")
    assert event.user is None
    assert event.username_snapshot == "manager2"


# --- history where the object is --------------------------------------------


@pytest.mark.django_db
def test_history_for_an_object_finds_its_events():
    server = Server.objects.create(name="web01", primary_ip="198.51.100.10")
    _event(resource_type="Server", resource_id=str(server.uuid), action=AuditAction.UPDATE)
    _event(resource_type="Server", resource_id="someone-else")

    history = history_for(server)

    assert len(history) == 1
    assert history[0].action == AuditAction.UPDATE


def test_the_server_page_shows_its_own_history(client, manager):
    server = Server.objects.create(name="web01", primary_ip="198.51.100.10")
    _event(
        resource_type="Server",
        resource_id=str(server.uuid),
        action=AuditAction.UPDATE,
        username_snapshot="alice",
    )
    client.force_login(manager)

    body = client.get(reverse("manage:server-detail", args=[server.uuid])).content.decode()

    assert "History" in body
    assert "alice" in body

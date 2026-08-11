"""Editing Ansible playbooks as files in the workspace."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from automation import workspace
from automation.workspace import (
    NotAPlaybook,
    UnsafePath,
    delete_playbook,
    list_playbooks,
    playbook_path,
    read_playbook,
    validate,
    write_playbook,
)

GOOD = """\
---
- name: Update every host
  hosts: all
  tasks:
    - name: Ping
      ansible.builtin.ping:
"""


@pytest.fixture
def ws(tmp_path, settings):
    """Point the workspace at a temporary directory for the whole test."""
    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    workspace.ensure_layout()
    return settings.ANSIBLE_WORKSPACE


# --- the workspace on disk --------------------------------------------------


def test_the_layout_is_a_standard_ansible_workspace(ws):
    for directory in ("inventories", "playbooks", "roles", "group_vars", "host_vars"):
        assert (ws / directory).is_dir()
    assert (ws / "ansible.cfg").is_file()


def test_an_existing_ansible_cfg_is_never_overwritten(ws):
    (ws / "ansible.cfg").write_text("[defaults]\nmine = yes\n")

    workspace.ensure_layout()

    assert "mine = yes" in (ws / "ansible.cfg").read_text()


def test_a_playbook_is_written_as_a_real_file(ws):
    write_playbook("update.yml", GOOD)

    assert (ws / "playbooks" / "update.yml").read_text() == GOOD


def test_a_nested_playbook_creates_its_directory(ws):
    write_playbook("linux/update.yml", GOOD)

    assert (ws / "playbooks" / "linux" / "update.yml").is_file()
    assert [p.name for p in list_playbooks()] == ["linux/update.yml"]


def test_carriage_returns_from_the_browser_are_normalised(ws):
    write_playbook("update.yml", "---\r\n- name: x\r\n")

    assert "\r" not in (ws / "playbooks" / "update.yml").read_text()


def test_reading_and_deleting_a_playbook(ws):
    write_playbook("update.yml", GOOD)

    assert read_playbook("update.yml") == GOOD

    delete_playbook("update.yml")
    assert not (ws / "playbooks" / "update.yml").exists()


def test_deleting_something_that_is_not_there_is_an_error(ws):
    with pytest.raises(FileNotFoundError):
        delete_playbook("nope.yml")


# --- refusing to write outside the workspace --------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd.yml",
        "..%2F..%2Fetc.yml",
        "/etc/cron.d/evil.yml",
        "playbooks/../../escape.yml",
        "",
        "   ",
    ],
)
def test_a_name_that_escapes_the_workspace_is_refused(ws, name):
    with pytest.raises((UnsafePath, NotAPlaybook)):
        playbook_path(name)


def test_only_yaml_suffixes_are_accepted(ws):
    with pytest.raises(NotAPlaybook):
        playbook_path("update.sh")


def test_a_symlink_pointing_out_of_the_workspace_is_refused(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (ws / "playbooks" / "escape").symlink_to(outside)

    with pytest.raises(UnsafePath):
        playbook_path("escape/evil.yml")


# --- validation -------------------------------------------------------------


def test_a_valid_playbook_has_no_problems():
    assert validate(GOOD) == []


def test_broken_yaml_is_reported_with_a_line_number():
    problems = validate("---\n- name: x\n   bad: [indent\n")

    assert len(problems) == 1
    assert "line" in problems[0]


def test_an_empty_file_is_reported():
    assert validate("") == ["The file is empty."]


def test_a_playbook_must_be_a_list_of_plays():
    problems = validate("hosts: all\ntasks: []\n")

    assert "list of plays" in problems[0]


def test_a_play_without_hosts_is_reported():
    problems = validate("---\n- name: x\n  tasks: []\n")

    assert any("no 'hosts'" in problem for problem in problems)


def test_a_play_that_would_do_nothing_is_reported():
    problems = validate("---\n- name: x\n  hosts: all\n")

    assert any("would do nothing" in problem for problem in problems)


def test_an_import_playbook_entry_is_accepted():
    assert validate("---\n- import_playbook: other.yml\n") == []


# --- the web surface --------------------------------------------------------


@pytest.fixture
def author(db):
    user = get_user_model().objects.create_user("author", password="playbook-pass-1")
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="automation",
            codename__in=[
                "view_playbook",
                "add_playbook",
                "change_playbook",
                "delete_playbook",
            ],
        )
    )
    return user


def test_the_list_needs_a_signed_in_user(client, ws):
    assert client.get(reverse("automation:playbooks")).status_code == 302


def test_a_user_without_permission_is_refused(client, ws, db):
    nobody = get_user_model().objects.create_user("nobody", password="playbook-pass-2")
    client.force_login(nobody)

    assert client.get(reverse("automation:playbooks")).status_code == 403


def test_the_list_shows_the_playbooks_on_disk(client, ws, author):
    write_playbook("linux/update.yml", GOOD)
    client.force_login(author)

    response = client.get(reverse("automation:playbooks"))

    assert response.status_code == 200
    assert "linux/update.yml" in response.content.decode()


def test_creating_a_playbook_writes_it(client, ws, author):
    client.force_login(author)

    response = client.post(
        reverse("automation:playbook-create"),
        {"name": "linux/update.yml", "content": GOOD},
    )

    assert response.status_code == 302
    assert read_playbook("linux/update.yml") == GOOD


def test_a_playbook_that_does_not_parse_is_not_written(client, ws, author):
    client.force_login(author)

    response = client.post(
        reverse("automation:playbook-create"),
        {"name": "broken.yml", "content": "---\n- name: x\n   bad: [indent\n"},
    )

    assert response.status_code == 200
    assert not (ws / "playbooks" / "broken.yml").exists()
    assert "Invalid YAML" in response.content.decode()


def test_editing_a_playbook_replaces_its_content(client, ws, author):
    write_playbook("update.yml", GOOD)
    client.force_login(author)
    changed = GOOD.replace("Update every host", "Patch every host")

    client.post(
        reverse("automation:playbook-edit", args=["update.yml"]),
        {"name": "update.yml", "content": changed},
    )

    assert "Patch every host" in read_playbook("update.yml")


def test_editing_a_playbook_that_does_not_exist_redirects(client, ws, author):
    client.force_login(author)

    response = client.get(reverse("automation:playbook-edit", args=["ghost.yml"]))

    assert response.status_code == 302


def test_deleting_a_playbook_asks_first(client, ws, author):
    write_playbook("update.yml", GOOD)
    client.force_login(author)

    response = client.get(reverse("automation:playbook-delete", args=["update.yml"]))

    assert response.status_code == 200
    assert (ws / "playbooks" / "update.yml").exists()


def test_deleting_a_playbook_on_post_removes_the_file(client, ws, author):
    write_playbook("update.yml", GOOD)
    client.force_login(author)

    client.post(reverse("automation:playbook-delete", args=["update.yml"]))

    assert not (ws / "playbooks" / "update.yml").exists()


def test_a_write_is_recorded_in_the_audit_trail(client, ws, author):
    from audit.models import AuditEvent

    client.force_login(author)
    client.post(reverse("automation:playbook-create"), {"name": "update.yml", "content": GOOD})

    event = AuditEvent.objects.filter(module="automation").latest("created_at")
    assert event.resource_id == "update.yml"
    assert event.username_snapshot == "author"

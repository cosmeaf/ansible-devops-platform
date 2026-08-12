"""The workspace as a file explorer: browse, create, rename, delete."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from audit.models import AuditAction, AuditEvent
from automation import workspace
from automation.workspace import NotEditable, UnsafePath

PLAY = "---\n- name: x\n  hosts: all\n  tasks: []\n"


@pytest.fixture
def ws(tmp_path, settings):
    settings.ANSIBLE_WORKSPACE = tmp_path / "ansible"
    workspace.ensure_layout()
    return settings.ANSIBLE_WORKSPACE


# --- the file API -----------------------------------------------------------


def test_the_root_lists_the_standard_layout(ws):
    names = [entry.name for entry in workspace.list_dir()]

    assert "playbooks" in names
    assert "roles" in names
    assert "ansible.cfg" in names


def test_folders_are_listed_before_files(ws):
    workspace.write_file("zzz.yml", PLAY)
    entries = workspace.list_dir()

    assert entries[0].is_dir is True
    assert entries[-1].name == "zzz.yml"
    assert [e.is_dir for e in entries] == sorted((e.is_dir for e in entries), reverse=True)


def test_a_nested_folder_can_be_created_and_listed(ws):
    workspace.create_dir("roles/nginx/tasks")
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)

    assert [e.name for e in workspace.list_dir("roles/nginx/tasks")] == ["main.yml"]


def test_creating_a_folder_that_exists_is_an_error(ws):
    workspace.create_dir("roles/nginx")

    with pytest.raises(FileExistsError):
        workspace.create_dir("roles/nginx")


def test_the_tree_nests_children(ws):
    workspace.write_file("playbooks/linux/update.yml", PLAY)
    tree = {node["entry"].name: node for node in workspace.tree()}

    playbooks = tree["playbooks"]
    linux = playbooks["children"][0]
    assert linux["entry"].name == "linux"
    assert linux["children"][0]["entry"].name == "update.yml"


def test_any_text_file_can_be_edited_not_only_playbooks(ws):
    workspace.write_file("group_vars/all.yml", "ntp_server: pool.ntp.org\n")

    assert "ntp_server" in workspace.read_file("group_vars/all.yml")
    assert "roles_path" in workspace.read_file("ansible.cfg")


def test_a_binary_suffix_is_not_opened(ws):
    (ws / "logo.png").write_bytes(b"\x89PNG\r\n")

    with pytest.raises(NotEditable):
        workspace.read_file("logo.png")


def test_a_file_too_large_to_edit_is_refused(ws):
    workspace.write_file("big.txt", "x")
    (ws / "big.txt").write_text("x" * (workspace.MAX_EDITABLE_BYTES + 1))

    with pytest.raises(NotEditable, match="too large"):
        workspace.read_file("big.txt")


def test_a_file_that_is_not_utf8_is_refused(ws):
    (ws / "broken.txt").write_bytes(b"\xff\xfe\x00binary")

    with pytest.raises(NotEditable, match="not text"):
        workspace.read_file("broken.txt")


def test_deleting_a_folder_removes_everything_under_it(ws):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    workspace.write_file("roles/nginx/handlers/main.yml", PLAY)

    removed = workspace.delete("roles/nginx")

    assert removed == 2
    assert not (ws / "roles" / "nginx").exists()


def test_counting_says_how_much_a_delete_would_take(ws):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    workspace.write_file("roles/nginx/handlers/main.yml", PLAY)

    assert workspace.count_files("roles/nginx") == 2
    assert workspace.count_files("roles/nginx/tasks/main.yml") == 1


def test_renaming_moves_a_file_between_folders(ws):
    workspace.write_file("playbooks/update.yml", PLAY)

    workspace.rename("playbooks/update.yml", "playbooks/linux/update.yml")

    assert (ws / "playbooks" / "linux" / "update.yml").is_file()
    assert not (ws / "playbooks" / "update.yml").exists()


def test_renaming_onto_something_that_exists_is_refused(ws):
    workspace.write_file("a.yml", PLAY)
    workspace.write_file("b.yml", PLAY)

    with pytest.raises(FileExistsError):
        workspace.rename("a.yml", "b.yml")


@pytest.mark.parametrize("path", ["../escape.yml", "/etc/passwd", "roles/../../out.yml", "..", ""])
def test_a_path_outside_the_workspace_is_refused(ws, path):
    with pytest.raises(UnsafePath):
        workspace.resolve(path)


def test_the_workspace_root_itself_cannot_be_deleted(ws):
    with pytest.raises(UnsafePath):
        workspace.resolve("", allow_root=False)


# --- the web surface --------------------------------------------------------


@pytest.fixture
def author(db):
    user = get_user_model().objects.create_user("filer", password="fixture-password-not-a-secret-1")
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="automation"))
    return user


def test_browsing_needs_permission(client, ws, db):
    nobody = get_user_model().objects.create_user(
        "nobody2", password="fixture-password-not-a-secret-1"
    )
    client.force_login(nobody)

    assert client.get(reverse("automation:browse")).status_code == 403


def test_the_explorer_shows_the_folders(client, ws, author):
    client.force_login(author)

    body = client.get(reverse("automation:browse")).content.decode()

    assert "playbooks" in body
    assert "roles" in body
    assert "group_vars" in body


def test_the_explorer_walks_into_a_folder(client, ws, author):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    client.force_login(author)

    body = client.get(reverse("automation:browse"), {"path": "roles/nginx"}).content.decode()

    assert "tasks" in body


def test_browsing_outside_the_workspace_is_refused(client, ws, author):
    client.force_login(author)

    response = client.get(reverse("automation:browse"), {"path": "../.."}, follow=True)

    assert "not a folder in the workspace" in response.content.decode()


def test_creating_a_file_from_the_web(client, ws, author):
    client.force_login(author)

    client.post(
        reverse("automation:create-file"),
        {"name": "group_vars/all.yml", "content": "ntp: pool.ntp.org\n"},
    )

    assert "ntp" in workspace.read_file("group_vars/all.yml")


def test_creating_a_folder_from_the_web(client, ws, author):
    client.force_login(author)

    client.post(reverse("automation:create-folder"), {"name": "roles/nginx/tasks"})

    assert (ws / "roles" / "nginx" / "tasks").is_dir()


def test_a_file_with_an_unsupported_extension_is_refused(client, ws, author):
    client.force_login(author)

    response = client.post(reverse("automation:create-file"), {"name": "run.bin", "content": "x"})

    assert response.status_code == 200
    assert not (ws / "run.bin").exists()


def test_broken_yaml_is_still_refused_in_the_general_editor(client, ws, author):
    workspace.write_file("group_vars/all.yml", "ntp: pool.ntp.org\n")
    client.force_login(author)

    response = client.post(
        f"{reverse('automation:edit')}?path=group_vars/all.yml",
        {"content": "key: [unclosed\n"},
    )

    assert response.status_code == 200
    assert "Invalid YAML" in response.content.decode()
    assert "pool.ntp.org" in workspace.read_file("group_vars/all.yml")


def test_a_non_yaml_file_is_saved_without_yaml_validation(client, ws, author):
    client.force_login(author)

    client.post(
        f"{reverse('automation:edit')}?path=ansible.cfg",
        {"content": "[defaults]\nforks = 10\n"},
    )

    assert "forks = 10" in workspace.read_file("ansible.cfg")


def test_renaming_from_the_web(client, ws, author):
    workspace.write_file("playbooks/update.yml", PLAY)
    client.force_login(author)

    client.post(
        f"{reverse('automation:rename')}?path=playbooks/update.yml",
        {"name": "playbooks/linux/update.yml"},
    )

    assert (ws / "playbooks" / "linux" / "update.yml").is_file()


def test_deleting_asks_first_and_says_how_much_would_go(client, ws, author):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    workspace.write_file("roles/nginx/handlers/main.yml", PLAY)
    client.force_login(author)

    body = client.get(f"{reverse('automation:delete')}?path=roles/nginx").content.decode()

    assert "2 files inside it" in body
    assert (ws / "roles" / "nginx").exists()


def test_deleting_a_folder_from_the_web(client, ws, author):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    client.force_login(author)

    client.post(f"{reverse('automation:delete')}?path=roles/nginx")

    assert not (ws / "roles" / "nginx").exists()


# --- traceability -----------------------------------------------------------


def test_deleting_records_who_did_it_and_what_went(client, ws, author):
    workspace.write_file("roles/nginx/tasks/main.yml", PLAY)
    workspace.write_file("roles/nginx/handlers/main.yml", PLAY)
    client.force_login(author)

    client.post(f"{reverse('automation:delete')}?path=roles/nginx")

    event = AuditEvent.objects.filter(action=AuditAction.DELETE).latest("created_at")
    assert event.username_snapshot == "filer"
    assert event.resource_id == "roles/nginx"
    assert event.previous_value["files"] == 2
    assert event.previous_value["kind"] == "folder"


def test_creating_and_editing_are_recorded_too(client, ws, author):
    client.force_login(author)

    client.post(reverse("automation:create-file"), {"name": "a.yml", "content": PLAY})
    client.post(f"{reverse('automation:edit')}?path=a.yml", {"content": PLAY})

    actions = list(AuditEvent.objects.filter(resource_id="a.yml").values_list("action", flat=True))
    assert AuditAction.CREATE in actions
    assert AuditAction.UPDATE in actions


def test_a_rename_records_where_it_came_from(client, ws, author):
    workspace.write_file("a.yml", PLAY)
    client.force_login(author)

    client.post(f"{reverse('automation:rename')}?path=a.yml", {"name": "b.yml"})

    event = AuditEvent.objects.filter(resource_id="b.yml").latest("created_at")
    assert event.previous_value["path"] == "a.yml"


def test_a_playbook_is_still_checked_as_a_playbook(client, ws, author):
    """Under playbooks/, a mapping is not a playbook and must be refused."""
    client.force_login(author)

    response = client.post(
        reverse("automation:create-file"),
        {"name": "playbooks/wrong.yml", "content": "hosts: all\ntasks: []\n"},
    )

    assert response.status_code == 200
    assert "list of plays" in response.content.decode()
    assert not (ws / "playbooks" / "wrong.yml").exists()


def test_group_vars_may_be_a_mapping(client, ws, author):
    """Outside playbooks/, YAML only has to parse."""
    client.force_login(author)

    client.post(
        reverse("automation:create-file"),
        {"name": "group_vars/webservers.yml", "content": "nginx_port: 8080\n"},
    )

    assert "nginx_port" in workspace.read_file("group_vars/webservers.yml")

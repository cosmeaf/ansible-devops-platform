from django.urls import path, register_converter

from . import files, views


class PlaybookNameConverter:
    """A workspace-relative playbook path, such as ``linux/update.yml``.

    Slashes are allowed so nested playbooks are addressable; the workspace
    module is what refuses anything that would escape the root.
    """

    regex = r"[A-Za-z0-9][A-Za-z0-9._/-]*"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(PlaybookNameConverter, "playbook")

app_name = "automation"

urlpatterns = [
    path("", views.playbooks, name="playbooks"),
    path("files/", files.browse, name="browse"),
    path("files/edit/", files.edit, name="edit"),
    path("files/new/", files.create_file, name="create-file"),
    path("files/new-folder/", files.create_folder, name="create-folder"),
    path("files/rename/", files.rename, name="rename"),
    path("files/delete/", files.delete, name="delete"),
    path("new/", views.playbook_create, name="playbook-create"),
    path("<playbook:name>/edit/", views.playbook_edit, name="playbook-edit"),
    path("<playbook:name>/delete/", views.playbook_delete, name="playbook-delete"),
]

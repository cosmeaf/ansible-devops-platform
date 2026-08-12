from django.urls import path

from . import files

app_name = "automation"

urlpatterns = [
    path("", files.browse_playbooks, name="playbooks"),
    path("files/", files.browse, name="browse"),
    path("files/edit/", files.edit, name="edit"),
    path("files/new/", files.create_file, name="create-file"),
    path("files/new-folder/", files.create_folder, name="create-folder"),
    path("files/rename/", files.rename, name="rename"),
    path("files/delete/", files.delete, name="delete"),
]

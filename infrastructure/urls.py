from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("servers/", views.servers, name="servers"),
    path("servers/new/", views.server_create, name="server-create"),
    path("servers/<uuid:uuid>/", views.server_detail, name="server-detail"),
    path("servers/<uuid:uuid>/edit/", views.server_edit, name="server-edit"),
    path("servers/<uuid:uuid>/delete/", views.server_delete, name="server-delete"),
    path("groups/", views.groups, name="groups"),
    path("groups/new/", views.group_create, name="group-create"),
    path("groups/<uuid:uuid>/edit/", views.group_edit, name="group-edit"),
    path("groups/<uuid:uuid>/delete/", views.group_delete, name="group-delete"),
    path("environments/", views.environments, name="environments"),
    path("environments/new/", views.environment_create, name="environment-create"),
    path("environments/<uuid:uuid>/edit/", views.environment_edit, name="environment-edit"),
    path("environments/<uuid:uuid>/delete/", views.environment_delete, name="environment-delete"),
    path("clients/", views.clients, name="clients"),
    path("clients/new/", views.client_create, name="client-create"),
    path("clients/<uuid:uuid>/edit/", views.client_edit, name="client-edit"),
    path("clients/<uuid:uuid>/delete/", views.client_delete, name="client-delete"),
    path("credentials/", views.credential_list, name="credentials"),
    path("credentials/new/", views.credential_create, name="credential-create"),
    path("credentials/<uuid:uuid>/edit/", views.credential_edit, name="credential-edit"),
    path("credentials/<uuid:uuid>/delete/", views.credential_delete, name="credential-delete"),
]

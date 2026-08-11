from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("servers/", views.servers, name="servers"),
    path("servers/new/", views.server_create, name="server-create"),
    path("servers/<uuid:uuid>/", views.server_detail, name="server-detail"),
    path("servers/<uuid:uuid>/edit/", views.server_edit, name="server-edit"),
    path("groups/", views.groups, name="groups"),
    path("groups/new/", views.group_create, name="group-create"),
    path("environments/", views.environments, name="environments"),
    path("environments/new/", views.environment_create, name="environment-create"),
    path("clients/", views.clients, name="clients"),
    path("clients/new/", views.client_create, name="client-create"),
    path("credentials/", views.credential_list, name="credentials"),
    path("credentials/new/", views.credential_create, name="credential-create"),
]

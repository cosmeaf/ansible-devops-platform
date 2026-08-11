from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("servers/", views.servers, name="servers"),
    path("servers/<uuid:uuid>/", views.server_detail, name="server-detail"),
    path("environments/", views.environments, name="environments"),
    path("groups/", views.groups, name="groups"),
]

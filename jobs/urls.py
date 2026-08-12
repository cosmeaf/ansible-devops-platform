from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_list, name="list"),
    path("run/", views.job_create, name="run"),
    path("<uuid:uuid>/", views.job_detail, name="detail"),
    path("<uuid:uuid>/status/", views.job_status, name="status"),
    path("<uuid:uuid>/delete/", views.job_delete, name="delete"),
    path("servers/<uuid:uuid>/test/", views.server_test, name="server-test"),
    path("servers/<uuid:uuid>/trust/", views.server_trust, name="server-trust"),
    path("servers/<uuid:uuid>/forget/", views.server_forget, name="server-forget"),
]

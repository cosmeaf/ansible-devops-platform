from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("audit/", views.audit_events, name="audit"),
    path("security/", views.security_events, name="security"),
    path("ip-intelligence/", views.ip_intelligence, name="ipintel"),
    path("settings/", views.platform_settings, name="settings"),
    path("users/", views.users, name="users"),
    path("roles/", views.roles, name="roles"),
]

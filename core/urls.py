from django.contrib import admin
from django.urls import include, path

from .views import dashboard, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("manage/", include("authentication.urls")),
    path("api/v1/health/", health, name="health"),
    path("", dashboard, name="dashboard"),
]

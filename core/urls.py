from django.contrib import admin
from django.urls import include, path

from .views import dashboard, health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("manage/inventory/", include("inventory.urls")),
    path("manage/", include("infrastructure.urls")),
    path("api/v1/health/", health, name="health"),
    path("api/v1/", include("core.api_urls")),
    path("", dashboard, name="dashboard"),
]

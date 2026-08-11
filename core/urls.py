from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/v1/health/", health, name="health"),
    path(
        "",
        TemplateView.as_view(template_name="dashboard/index.html"),
        name="dashboard",
    ),
]

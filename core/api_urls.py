"""Versioned REST API routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from credentials.api import CredentialViewSet
from infrastructure.api import (
    ClientViewSet,
    EnvironmentViewSet,
    ServerGroupViewSet,
    ServerViewSet,
)

router = DefaultRouter()
router.register("servers", ServerViewSet, basename="server")
router.register("server-groups", ServerGroupViewSet, basename="servergroup")
router.register("environments", EnvironmentViewSet, basename="environment")
router.register("clients", ClientViewSet, basename="client")
router.register("credentials", CredentialViewSet, basename="credential")

urlpatterns = [path("", include(router.urls))]

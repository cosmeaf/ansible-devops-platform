"""REST API for managed infrastructure."""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import DjangoModelPermissions

from audit.models import AuditAction
from commun.audit_mixins import AuditedModelMixin

from .models import Client, Environment, Server, ServerGroup
from .serializers import (
    ClientSerializer,
    EnvironmentSerializer,
    ServerGroupSerializer,
    ServerSerializer,
)


class EnvironmentViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
    permission_classes = [DjangoModelPermissions]
    lookup_field = "uuid"
    audit_module = "infrastructure"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["active", "require_check_mode"]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]


class ClientViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [DjangoModelPermissions]
    lookup_field = "uuid"
    audit_module = "infrastructure"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["active"]
    search_fields = ["name", "slug", "description", "contact_email"]
    ordering_fields = ["name", "created_at"]


class ServerGroupViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = ServerGroup.objects.all()
    serializer_class = ServerGroupSerializer
    permission_classes = [DjangoModelPermissions]
    lookup_field = "uuid"
    audit_module = "infrastructure"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at"]


class ServerViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Server.objects.select_related("environment").prefetch_related("groups")
    serializer_class = ServerSerializer
    permission_classes = [DjangoModelPermissions]
    lookup_field = "uuid"
    audit_module = "infrastructure"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "status": ["exact"],
        "active": ["exact"],
        "operating_system": ["exact"],
        "connection_method": ["exact"],
        "environment__slug": ["exact"],
        "client__slug": ["exact"],
        "groups__slug": ["exact"],
    }
    search_fields = ["name", "hostname", "primary_ip", "description"]
    ordering_fields = ["name", "status", "created_at"]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        self._record(AuditAction.CREATE, instance, new=serializer.data)

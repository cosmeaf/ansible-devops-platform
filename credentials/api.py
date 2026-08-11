"""REST API for credentials.

The secret is write-only at the serializer level, so no endpoint here can
return one. ``use`` is modelled as a separate permission from ``view``.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import DjangoModelPermissions

from audit.models import AuditAction
from commun.audit_mixins import AuditedModelMixin

from .models import Credential
from .serializers import CredentialSerializer


class CredentialViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Credential.objects.all()
    serializer_class = CredentialSerializer
    permission_classes = [DjangoModelPermissions]
    lookup_field = "uuid"
    audit_module = "credentials"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["type"]
    search_fields = ["name", "description", "username"]
    ordering_fields = ["name", "created_at", "last_used_at"]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        # serializer.data excludes the write-only secret, so the audit payload
        # is safe by construction as well as by redaction.
        self._record(AuditAction.CREATE, instance, new=serializer.data)

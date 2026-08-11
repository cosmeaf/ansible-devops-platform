"""Write an audit event for every mutating API call.

Placed in ``commun`` because every module's viewsets need it. The mixin records
create, update and delete against :class:`~audit.models.AuditEvent`, carrying
the request id set by the audit middleware so an API call can be traced into
the logs.

Payloads pass through the audit sanitizer on save, so a serializer that
accidentally carries a secret still cannot write one to the trail.
"""

from audit.models import AuditAction, AuditEvent, AuditResult


class AuditedModelMixin:
    """Mix into a DRF ``ModelViewSet``.

    Set ``audit_module`` to the module name recorded on each event.
    """

    audit_module = "unknown"

    def _record(self, action, instance, *, previous=None, new=None):
        request = self.request
        user = request.user if request.user.is_authenticated else None
        AuditEvent.objects.create(
            user=user,
            username_snapshot=user.get_username() if user else "",
            request_id=getattr(request, "request_id", "") or "",
            session_id=request.session.session_key or "",
            source_ip=self._client_ip(request),
            module=self.audit_module,
            resource_type=instance.__class__.__name__,
            resource_id=str(getattr(instance, "uuid", "") or instance.pk),
            action=action,
            previous_value=previous,
            new_value=new,
            result=AuditResult.SUCCESS,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # Left-most entry is the original client; the rest are proxies.
            return forwarded.split(",")[0].strip() or None
        return request.META.get("REMOTE_ADDR") or None

    def perform_create(self, serializer):
        instance = serializer.save()
        self._record(AuditAction.CREATE, instance, new=serializer.data)

    def perform_update(self, serializer):
        previous = self.get_serializer(serializer.instance).data
        instance = serializer.save()
        self._record(AuditAction.UPDATE, instance, previous=previous, new=serializer.data)

    def perform_destroy(self, instance):
        previous = self.get_serializer(instance).data
        identifier = str(getattr(instance, "uuid", "") or instance.pk)
        resource_type = instance.__class__.__name__
        instance.delete()
        # Recorded after the delete, so the trail only claims what happened.
        request = self.request
        user = request.user if request.user.is_authenticated else None
        AuditEvent.objects.create(
            user=user,
            username_snapshot=user.get_username() if user else "",
            request_id=getattr(request, "request_id", "") or "",
            source_ip=self._client_ip(request),
            module=self.audit_module,
            resource_type=resource_type,
            resource_id=identifier,
            action=AuditAction.DELETE,
            previous_value=previous,
            result=AuditResult.SUCCESS,
        )

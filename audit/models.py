"""Immutable audit trail for platform activity."""

from django.conf import settings
from django.db import models

from commun.models import BaseModel

from .sanitizers import sanitize


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    READ = "READ", "Read"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    EXECUTE = "EXECUTE", "Execute"
    CHECK = "CHECK", "Check"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    DENIED = "DENIED", "Denied"
    EXPORT = "EXPORT", "Export"
    DOWNLOAD = "DOWNLOAD", "Download"


class AuditResult(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    DENIED = "DENIED", "Denied"


class AuditEvent(BaseModel):
    """A single recorded action.

    ``username_snapshot`` is stored alongside the ``user`` foreign key so the
    trail survives account deletion, which sets ``user`` to NULL.

    Every JSON payload is redacted on save — see :mod:`audit.sanitizers`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    session_id = models.CharField(max_length=64, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    asn = models.CharField(max_length=32, blank=True)
    module = models.CharField(max_length=100, db_index=True)
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=128, blank=True)
    action = models.CharField(max_length=16, choices=AuditAction.choices)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    result = models.CharField(
        max_length=16, choices=AuditResult.choices, default=AuditResult.SUCCESS
    )
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "audit event"
        verbose_name_plural = "audit events"
        indexes = [
            models.Index(fields=["-created_at", "module"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "result"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self) -> str:
        actor = self.username_snapshot or "anonymous"
        return f"{self.action} {self.module} by {actor} ({self.result})"

    def save(self, *args, **kwargs):
        self.previous_value = sanitize(self.previous_value)
        self.new_value = sanitize(self.new_value)
        self.metadata = sanitize(self.metadata or {})
        if self.user and not self.username_snapshot:
            self.username_snapshot = self.user.get_username()
        return super().save(*args, **kwargs)

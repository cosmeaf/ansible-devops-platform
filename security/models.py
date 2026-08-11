"""Security event records.

This module deliberately only *records* events. Enforcement (IP blocking,
lockout thresholds) is on the roadmap and will land with tests rather than as
an untested aggressive default — see ROADMAP.md.
"""

from django.conf import settings
from django.db import models

from commun.models import BaseModel


class SecurityEventType(models.TextChoices):
    FAILED_LOGIN = "FAILED_LOGIN", "Failed login"
    BLOCKED_IP = "BLOCKED_IP", "Blocked IP"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY", "Suspicious activity"
    POLICY_CHANGE = "POLICY_CHANGE", "Policy change"
    SESSION_EVENT = "SESSION_EVENT", "Session event"


class SecuritySeverity(models.TextChoices):
    INFO = "INFO", "Info"
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class SecurityEvent(BaseModel):
    event_type = models.CharField(max_length=32, choices=SecurityEventType.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )
    source_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    severity = models.CharField(
        max_length=16, choices=SecuritySeverity.choices, default=SecuritySeverity.INFO
    )
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "security event"
        verbose_name_plural = "security events"
        indexes = [
            models.Index(fields=["-created_at", "event_type"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} [{self.severity}] from {self.source_ip or 'unknown'}"

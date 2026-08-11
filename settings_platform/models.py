"""Operational platform configuration stored in the database.

Scope boundary: infrastructure secrets (database password, Django secret key,
encryption key) live in ``.env`` and are never written here. This table holds
operational settings an administrator may change at runtime.
"""

from django.db import models

from commun.models import BaseModel

REDACTED = "[REDACTED]"


class PlatformSetting(BaseModel):
    category = models.CharField(max_length=50)
    key = models.CharField(max_length=100)
    value = models.JSONField(default=dict)
    is_secret = models.BooleanField(
        default=False,
        help_text="Hide this value from listings and API representations.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "key"]
        verbose_name = "platform setting"
        verbose_name_plural = "platform settings"
        constraints = [
            models.UniqueConstraint(fields=["category", "key"], name="unique_platform_setting")
        ]

    def __str__(self) -> str:
        return f"{self.category}.{self.key}"

    @property
    def display_value(self):
        """Value safe to render in listings, logs and API responses."""
        return REDACTED if self.is_secret else self.value

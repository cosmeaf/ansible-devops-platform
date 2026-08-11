"""Stored IP intelligence records."""

from django.db import models

from commun.models import BaseModel


class IPIntelligence(BaseModel):
    """What the platform knows about a single IP address.

    Records are enriched by a provider (see :mod:`ipintel.providers`). The
    built-in local provider only classifies public vs. private; commercial
    lookups are optional and never required for the platform to run.
    """

    ip = models.GenericIPAddressField(unique=True)
    is_private = models.BooleanField(default=False)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=120, blank=True)
    asn = models.CharField(max_length=32, blank=True)
    network = models.CharField(max_length=128, blank=True)
    proxy_signal = models.BooleanField(default=False)
    vpn_signal = models.BooleanField(default=False)
    trusted = models.BooleanField(default=False)
    provider = models.CharField(max_length=50, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["ip"]
        verbose_name = "IP intelligence record"
        verbose_name_plural = "IP intelligence records"
        indexes = [
            models.Index(fields=["is_private"]),
            models.Index(fields=["trusted"]),
        ]

    def __str__(self) -> str:
        scope = "private" if self.is_private else "public"
        return f"{self.ip} ({scope})"

"""Shared abstract base models.

Only genuinely cross-cutting building blocks belong here — this package is not
a home for loose helper functions.
"""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Adds an external, non-sequential identifier safe to expose over the API."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Adds creation and last-modification timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """Default base for platform models: external UUID plus timestamps."""

    class Meta:
        abstract = True

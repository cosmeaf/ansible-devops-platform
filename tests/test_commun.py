"""Shared base model behaviour, verified through a concrete subclass."""

import uuid

import pytest

from audit.models import AuditEvent
from commun.models import BaseModel, TimeStampedModel, UUIDModel


def test_base_models_are_abstract():
    assert UUIDModel._meta.abstract is True
    assert TimeStampedModel._meta.abstract is True
    assert BaseModel._meta.abstract is True


@pytest.mark.django_db
def test_subclass_receives_a_unique_uuid():
    first = AuditEvent.objects.create(module="m", action="READ")
    second = AuditEvent.objects.create(module="m", action="READ")

    assert isinstance(first.uuid, uuid.UUID)
    assert first.uuid != second.uuid


@pytest.mark.django_db
def test_updated_at_advances_on_save():
    event = AuditEvent.objects.create(module="m", action="READ")
    original = event.updated_at

    event.module = "changed"
    event.save()
    event.refresh_from_db()

    assert event.updated_at > original


@pytest.mark.django_db
def test_created_at_is_stable_across_saves():
    event = AuditEvent.objects.create(module="m", action="READ")
    created = event.created_at

    event.module = "changed"
    event.save()
    event.refresh_from_db()

    assert event.created_at == created


@pytest.mark.django_db
def test_uuid_is_not_editable():
    field = AuditEvent._meta.get_field("uuid")

    assert field.editable is False
    assert field.unique is True

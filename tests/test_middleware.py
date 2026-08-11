"""Request-id propagation and log correlation."""

import logging
import uuid

import pytest
from django.urls import reverse

from audit.context import request_id_var
from audit.logging import RequestIDFilter


@pytest.mark.django_db
def test_response_carries_a_generated_request_id(client):
    response = client.get(reverse("dashboard"))

    assert "X-Request-ID" in response
    uuid.UUID(response["X-Request-ID"])  # raises if not a valid UUID


@pytest.mark.django_db
def test_inbound_request_id_is_preserved(client):
    incoming = "trace-abc-123"

    response = client.get(reverse("dashboard"), headers={"x-request-id": incoming})

    assert response["X-Request-ID"] == incoming


@pytest.mark.django_db
def test_request_id_context_is_reset_after_the_response(client):
    client.get(reverse("dashboard"))

    assert request_id_var.get() is None


@pytest.mark.django_db
def test_each_request_gets_a_distinct_id(client):
    first = client.get(reverse("dashboard"))["X-Request-ID"]
    second = client.get(reverse("dashboard"))["X-Request-ID"]

    assert first != second


def test_log_filter_uses_placeholder_outside_a_request():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)

    assert RequestIDFilter().filter(record) is True
    assert record.request_id == "-"


def test_log_filter_attaches_the_active_request_id():
    token = request_id_var.set("req-42")
    try:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
        RequestIDFilter().filter(record)
        assert record.request_id == "req-42"
    finally:
        request_id_var.reset(token)

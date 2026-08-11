"""Logging integration for the audit request context."""

import logging

from .context import request_id_var


class RequestIDFilter(logging.Filter):
    """Attach the current request id to every log record.

    Records emitted outside a request (management commands, Celery workers)
    get a stable ``-`` placeholder so the log format stays aligned.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True

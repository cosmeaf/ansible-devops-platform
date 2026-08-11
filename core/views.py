"""Core service views: liveness/readiness reporting."""

import logging

import redis
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
    except Exception:
        # Logged, never surfaced: the response must not leak a DSN or
        # credentials to an unauthenticated caller.
        logger.warning("Health check: database unreachable", exc_info=True)
        return False


def _check_redis() -> bool:
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            socket_timeout=1,
            socket_connect_timeout=1,
        )
        return bool(client.ping())
    except Exception:
        logger.warning("Health check: redis unreachable", exc_info=True)
        return False


@require_GET
def dashboard(request):
    """Site root.

    There is no separate landing page: the product is Ansible management, so an
    authenticated user goes straight there and everyone else goes to sign in.
    """
    if request.user.is_authenticated:
        return redirect("manage:overview")
    return redirect("login")


@require_GET
def health(request):
    """Report platform readiness.

    Returns 200 when every dependency answers, 503 otherwise, so container
    orchestrators and load balancers can act on it directly. The payload is
    intentionally limited to booleans — no hostnames, no connection strings.
    """
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    healthy = all(checks.values())
    payload = {
        "status": "healthy" if healthy else "degraded",
        "version": settings.VERSION,
        **checks,
    }
    return JsonResponse(payload, status=200 if healthy else 503)

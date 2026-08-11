"""Redaction helpers so audit records never persist credential material.

Audit is a security control: an audit trail that stores the password it was
recording an attempt against is worse than no audit trail at all. Every value
written to :class:`~audit.models.AuditEvent` passes through :func:`sanitize`.
"""

from typing import Any

REDACTED = "[REDACTED]"

#: Substrings that mark a key as credential-bearing. Matching is case
#: insensitive and substring based, so ``new_password`` and ``X-Api-Key`` are
#: both caught.
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "cookie",
    "authorization",
    "auth_header",
    "session_key",
    "sessionid",
    "csrfmiddlewaretoken",
    "credential",
    "passphrase",
    "salt",
    "signature",
    "encryption_key",
)

#: Maximum nesting depth we will walk. Anything deeper is replaced wholesale
#: rather than risking unbounded recursion on a cyclic structure.
MAX_DEPTH = 12


def is_sensitive_key(key: Any) -> bool:
    """Return ``True`` when *key* names a field that may carry a secret."""
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def sanitize(value: Any, _depth: int = 0) -> Any:
    """Recursively redact credential-bearing entries in *value*.

    Mappings are walked by key, sequences element-wise. Non-container values
    are returned untouched — redaction is driven by the key that names them,
    not by guessing at the shape of the value.
    """
    if _depth > MAX_DEPTH:
        return REDACTED

    if isinstance(value, dict):
        return {
            key: REDACTED if is_sensitive_key(key) else sanitize(item, _depth + 1)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        cleaned = [sanitize(item, _depth + 1) for item in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned

    return value


def sanitize_headers(headers: Any) -> dict:
    """Redact an HTTP header mapping, preserving the header names."""
    return {
        name: REDACTED if is_sensitive_key(name) else str(item)
        for name, item in dict(headers).items()
    }

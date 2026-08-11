"""Symmetric encryption for stored credential material.

The key comes from ``PLATFORM_ENCRYPTION_KEY`` in the environment — generated
at bootstrap, never stored in the database. That separation is the point: a
database dump on its own does not yield any secret.

Fernet gives authenticated encryption (AES-128-CBC + HMAC-SHA256), so a
tampered ciphertext fails to decrypt rather than returning garbage.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DecryptionError(Exception):
    """Raised when a stored secret cannot be decrypted.

    Almost always means ``PLATFORM_ENCRYPTION_KEY`` changed or the row was
    tampered with — both worth surfacing loudly rather than silently.
    """


def _fernet() -> Fernet:
    raw = getattr(settings, "PLATFORM_ENCRYPTION_KEY", "") or ""
    if not raw:
        raise ImproperlyConfigured(
            "PLATFORM_ENCRYPTION_KEY is not set. Run scripts/bootstrap.sh, which "
            "generates one, or set it in the environment."
        )
    # The bootstrap emits 32 random bytes as hex. Fernet wants a urlsafe-base64
    # 32-byte key, so hash whatever we are given to a fixed 32 bytes and encode.
    # Hashing also means a key of any length or format works.
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext*, returning a string safe to store in a text column."""
    if plaintext is None:
        raise ValueError("Cannot encrypt None.")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Decrypt a value produced by :func:`encrypt`."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError(
            "Stored secret could not be decrypted. Has PLATFORM_ENCRYPTION_KEY changed?"
        ) from exc

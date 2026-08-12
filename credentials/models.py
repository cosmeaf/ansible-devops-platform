"""Stored credentials for connecting to managed hosts.

Two rules govern this module:

* **A secret is never returned once stored.** Not by the API, not by the admin,
  not by ``__str__``. It is decrypted only at the moment a job needs it.
* **``use`` is a different permission from ``read``.** An operator may run a
  playbook with a credential without ever being able to see it.
"""

from django.conf import settings
from django.db import models

from commun.models import BaseModel

from .crypto import decrypt, encrypt


class CredentialType(models.TextChoices):
    SSH_PRIVATE_KEY = "SSH_PRIVATE_KEY", "SSH private key"
    SSH_PASSWORD = "SSH_PASSWORD", "SSH password"
    BECOME_PASSWORD = "BECOME_PASSWORD", "Become (sudo) password"


class Credential(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=32, choices=CredentialType.choices)
    username = models.CharField(
        max_length=64,
        blank=True,
        help_text="Remote user this credential authenticates as, when applicable.",
    )

    #: Ciphertext. Never exposed through a serializer, admin field or log line.
    encrypted_secret = models.TextField(editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credentials_created",
    )
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "credential"
        verbose_name_plural = "credentials"
        indexes = [models.Index(fields=["type"])]
        permissions = [
            (
                "use_credential",
                "Can use a credential to connect, without reading its secret",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"

    def set_secret(self, plaintext: str) -> None:
        """Encrypt and store *plaintext*. The only way in."""
        if not plaintext:
            raise ValueError("A credential secret cannot be empty.")
        self.encrypted_secret = encrypt(plaintext)

    def reveal_secret(self) -> str:
        """Decrypt the stored secret.

        Deliberately named so that a call site is obvious in review. Only the
        execution path should ever call this, never a serializer or a view.
        """
        return decrypt(self.encrypted_secret)

    @property
    def has_secret(self) -> bool:
        return bool(self.encrypted_secret)

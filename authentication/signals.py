"""Keep the derived user flags in step with role assignments."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import UserRole, sync_flags


@receiver(post_save, sender=UserRole)
def on_role_assigned(sender, instance, **kwargs):
    sync_flags(instance.user)


@receiver(post_delete, sender=UserRole)
def on_role_revoked(sender, instance, **kwargs):
    # The user row may already be gone when the cascade came from deleting the
    # user itself; there is nothing to resynchronise in that case.
    if instance.user_id and type(instance.user).objects.filter(pk=instance.user_id).exists():
        sync_flags(instance.user)

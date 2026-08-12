"""Automation content lives on disk, so this app owns almost no data.

Playbooks are files in the workspace, not rows. What the database still needs
is something to hang permissions on: RBAC in Django is expressed per model, and
"who may edit a playbook" is a question the platform has to be able to answer.
"""

from django.db import models


class Playbook(models.Model):
    """Permission anchor for the workspace playbooks. Never stored.

    ``managed = False`` means no table is created — only the four permissions,
    which the roles in ``seed_roles`` then pick up like any other.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_playbook", "Can view playbooks"),
            ("add_playbook", "Can create playbooks"),
            ("change_playbook", "Can edit playbooks"),
            ("delete_playbook", "Can delete playbooks"),
        ]
        verbose_name = "playbook"

    def __str__(self) -> str:  # pragma: no cover - never instantiated
        return "playbook"

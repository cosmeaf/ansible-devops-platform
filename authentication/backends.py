"""Authorisation backend that resolves permissions through roles."""

from django.contrib.auth.backends import BaseBackend

from .models import Role


class RolePermissionBackend(BaseBackend):
    """Grants a user every permission carried by their roles.

    Authentication is left to Django's ``ModelBackend``; this backend only
    answers permission questions, so the two compose without conflict.
    """

    def authenticate(self, request, **kwargs):
        return None

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return set()

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()

        cached = getattr(user_obj, "_role_perm_cache", None)
        if cached is not None:
            return cached

        permissions = {
            f"{label}.{codename}"
            for label, codename in Role.objects.filter(assignments__user=user_obj)
            .values_list("permissions__content_type__app_label", "permissions__codename")
            .distinct()
            if label and codename
        }
        user_obj._role_perm_cache = permissions
        return permissions

    def has_perm(self, user_obj, perm, obj=None):
        return perm in self.get_all_permissions(user_obj, obj=obj)

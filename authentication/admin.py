"""Django Admin registrations for access control.

Django Admin is the operator surface for platform internals — roles, users,
audit, security. The platform's own interface at /manage/ is for managing
Ansible. See docs/adr/0012-admin-is-not-product-surface.md.
"""

from django.contrib import admin

from .models import Role, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("role",)
    readonly_fields = ("assigned_by", "created_at")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "permission_count",
        "grants_admin_access",
        "grants_superuser",
        "is_system",
    )
    list_filter = ("grants_admin_access", "grants_superuser", "is_system")
    search_fields = ("name", "slug", "description")
    filter_horizontal = ("permissions",)
    readonly_fields = ("uuid", "is_system", "created_at", "updated_at")
    ordering = ("name",)

    @admin.display(description="permissions")
    def permission_count(self, obj: Role) -> int:
        return obj.permissions.count()

    def has_delete_permission(self, request, obj=None):
        # System roles must survive: a deployment must never be able to delete
        # the only role that grants it a way back in.
        if obj is not None and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_by", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "role__name")
    autocomplete_fields = ("user", "role")
    readonly_fields = ("uuid", "created_at", "updated_at")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        if not change and obj.assigned_by is None:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

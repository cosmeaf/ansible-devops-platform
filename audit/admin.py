from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only admin view.

    The audit trail is append-only by design; it is written by the platform,
    never edited by an operator.
    """

    list_display = (
        "created_at",
        "username_snapshot",
        "module",
        "action",
        "result",
        "resource_type",
        "resource_id",
        "source_ip",
    )
    list_filter = ("action", "result", "module", "created_at")
    search_fields = (
        "username_snapshot",
        "request_id",
        "resource_id",
        "resource_type",
        "source_ip",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib import admin

from .models import Environment, Server, ServerGroup


@admin.register(Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "require_check_mode", "server_count")
    list_filter = ("active", "require_check_mode")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("uuid", "created_at", "updated_at")

    @admin.display(description="servers")
    def server_count(self, obj):
        return obj.servers.count()


@admin.register(ServerGroup)
class ServerGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "member_count")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("uuid", "created_at", "updated_at")


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "ansible_host",
        "ssh_port",
        "ansible_user",
        "environment",
        "status",
        "active",
    )
    list_filter = ("status", "environment", "operating_system", "active", "groups")
    search_fields = ("name", "hostname", "primary_ip", "description")
    filter_horizontal = ("groups",)
    autocomplete_fields = ("environment",)
    readonly_fields = (
        "uuid",
        "status",
        "last_connection_test",
        "last_successful_connection",
        "created_by",
        "created_at",
        "updated_at",
    )

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

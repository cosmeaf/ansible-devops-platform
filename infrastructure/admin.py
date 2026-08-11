from django.contrib import admin

from .models import Client, Environment, Server, ServerGroup


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


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "contact_email", "active", "server_count")
    list_filter = ("active",)
    search_fields = ("name", "slug", "description", "contact_email")
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
        "connection_method",
        "operating_system",
        "client",
        "environment",
        "status",
    )
    list_filter = (
        "status",
        "connection_method",
        "operating_system",
        "environment",
        "client",
        "active",
        "groups",
    )
    search_fields = ("name", "hostname", "primary_ip", "description")
    filter_horizontal = ("groups",)
    autocomplete_fields = ("environment", "client", "credential")
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

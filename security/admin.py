from django.contrib import admin

from .models import SecurityEvent


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "severity", "user", "source_ip")
    list_filter = ("event_type", "severity", "created_at")
    search_fields = ("source_ip", "description", "user__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    readonly_fields = ("uuid", "created_at", "updated_at")

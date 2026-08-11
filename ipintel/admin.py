from django.contrib import admin

from .models import IPIntelligence


@admin.register(IPIntelligence)
class IPIntelligenceAdmin(admin.ModelAdmin):
    list_display = ("ip", "is_private", "trusted", "country", "asn", "provider")
    list_filter = ("is_private", "trusted", "proxy_signal", "vpn_signal", "provider")
    search_fields = ("ip", "asn", "network", "country", "city")
    ordering = ("ip",)
    list_per_page = 50
    readonly_fields = ("uuid", "created_at", "updated_at")

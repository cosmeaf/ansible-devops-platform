from django.contrib import admin

from .models import PlatformSetting


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ("category", "key", "masked_value", "is_secret", "updated_at")
    list_filter = ("category", "is_secret")
    search_fields = ("category", "key", "description")
    ordering = ("category", "key")
    list_per_page = 50
    readonly_fields = ("uuid", "created_at", "updated_at")

    @admin.display(description="value")
    def masked_value(self, obj: PlatformSetting):
        """Never render a value flagged secret in the changelist."""
        return obj.display_value

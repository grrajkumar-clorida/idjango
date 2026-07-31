from django.contrib import admin

from .models import AppSettings, Config


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ("key", "masked_value")
    search_fields = ("key",)

    @admin.display(description="value")
    def masked_value(self, obj):
        value = obj.value or ""
        if obj.key == "BREEZE_SESSION":
            if len(value) > 6:
                return f"{value[:4]}…{value[-2:]} (session token)"
            return "•••• (session token)"
        if len(value) <= 8:
            return "••••"
        return f"{value[:4]}…{value[-4:]}"


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("attribute", "value", "fetched_at")
    list_filter = ("fetched_at",)
    search_fields = ("attribute",)

from django.contrib import admin

from .models import ScanResult


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "verdict", "ai_likelihood", "created_at")
    list_filter = ("verdict", "created_at")
    search_fields = ("original_filename",)
    readonly_fields = [f.name for f in ScanResult._meta.fields]

    def has_add_permission(self, request):
        return False

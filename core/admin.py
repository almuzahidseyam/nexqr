from django.contrib import admin
from .models import DynamicQR, ScanAnalytics

@admin.register(DynamicQR)
class DynamicQRAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code', 'is_encrypted', 'is_artistic', 'created_at')
    search_fields = ('name', 'short_code', 'original_url')
    list_filter = ('is_encrypted', 'is_artistic')

@admin.register(ScanAnalytics)
class ScanAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('qr_code', 'ip_address', 'device_type', 'scanned_at')
    search_fields = ('ip_address', 'user_agent')
    list_filter = ('device_type', 'scanned_at')

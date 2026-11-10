from django.contrib import admin

from .models import Camera, RentalRate


class RentalRateInline(admin.TabularInline):
    model = RentalRate
    extra = 0


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "available_units", "deposit_amount", "is_active")
    list_filter = ("brand", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RentalRateInline]


@admin.register(RentalRate)
class RentalRateAdmin(admin.ModelAdmin):
    list_display = ("camera", "label", "duration_hours", "amount", "is_active")
    list_filter = ("camera__brand", "is_active")
    search_fields = ("camera__name",)

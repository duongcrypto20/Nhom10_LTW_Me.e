
from django.contrib import admin

from customers.models import CustomerProfile
from .models import Camera, RentalRate


# KIỂM TRA QUYỀN THÊM THIẾT BỊ
def can_add_catalog(request):
    if request.user.is_superuser:
        return True

    profile = getattr(
        request.user,
        "customer_profile",
        None,
    )

    return bool(
        profile
        and profile.role == CustomerProfile.Role.MANAGER
    )


# GÓI THUÊ TRONG CHI TIẾT MÁY
class RentalRateInline(admin.TabularInline):
    model = RentalRate
    extra = 0

    def has_add_permission(self, request, obj=None):
        return (
            can_add_catalog(request)
            and super().has_add_permission(request, obj)
        )


# QUẢN TRỊ MÁY ẢNH
@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "available_units",
        "deposit_amount",
        "is_active",
    )

    list_filter = ("brand", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RentalRateInline]

    def has_add_permission(self, request):
        return (
            can_add_catalog(request)
            and super().has_add_permission(request)
        )


# QUẢN TRỊ GÓI THUÊ
@admin.register(RentalRate)
class RentalRateAdmin(admin.ModelAdmin):
    list_display = (
        "camera",
        "label",
        "duration_hours",
        "amount",
        "is_active",
    )

    list_filter = ("camera__brand", "is_active")
    search_fields = ("camera__name",)

    def has_add_permission(self, request):
        return (
            can_add_catalog(request)
            and super().has_add_permission(request)
        )

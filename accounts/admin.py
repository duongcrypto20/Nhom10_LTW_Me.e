from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class TaiKhoanAdmin(UserAdmin):
    list_display = ('username', 'ho_ten', 'vai_tro', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Thông tin thêm', {'fields': ('ho_ten', 'so_dien_thoai', 'cccd', 'anh_dai_dien', 'vai_tro')}),
    )

    def save_model(self, request, obj, form, change):
        obj.is_staff = obj.vai_tro == User.CHU_CUA_HANG
        obj.is_superuser = obj.vai_tro == User.CHU_CUA_HANG
        super().save_model(request, obj, form, change)

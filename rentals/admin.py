"""Trang admin của app rentals: chỉ để xem, mọi thao tác nghiệp vụ làm trên website."""
from django.contrib import admin

from .models import ChiTietDonThue, DonThue, GiaoDich, PhanBoMay, ThongBao


class ChiXemAdmin(admin.ModelAdmin):
    """
    Admin chỉ đọc.

    Đơn thuê và tiền cọc phải đi qua các màn hình có kiểm tra (services.py),
    nên không cho thêm, sửa, xóa trực tiếp ở admin.
    """

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DonThue)
class DonThueAdmin(ChiXemAdmin):
    list_display = ('ma', 'khach_hang', 'thiet_bi', 'gio_nhan', 'trang_thai', 'trang_thai_coc')
    list_filter = ('trang_thai', 'trang_thai_coc')


@admin.register(GiaoDich)
class GiaoDichAdmin(ChiXemAdmin):
    list_display = ('don', 'loai', 'so_tien', 'phuong_thuc', 'ngay_tao')
    list_filter = ('loai', 'phuong_thuc')


admin.site.register(ChiTietDonThue, ChiXemAdmin)
admin.site.register(PhanBoMay, ChiXemAdmin)
admin.site.register(ThongBao, ChiXemAdmin)

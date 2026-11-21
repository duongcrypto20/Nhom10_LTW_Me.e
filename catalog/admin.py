"""Đăng ký các bảng của app catalog vào trang admin Django."""
from django.contrib import admin

from .models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi


@admin.register(ThietBi)
class ThietBiAdmin(admin.ModelAdmin):
    list_display = ('ma', 'ten', 'hang', 'danh_muc', 'tien_coc', 'ngung_cung_cap')
    search_fields = ('ma', 'ten', 'hang')


@admin.register(May)
class MayAdmin(admin.ModelAdmin):
    list_display = ('so_seri', 'thiet_bi', 'tinh_trang')
    list_filter = ('tinh_trang',)


admin.site.register(LoaiThietBi)
admin.site.register(GoiThue)
admin.site.register(GiaThue)
admin.site.register(MaGiamGia)

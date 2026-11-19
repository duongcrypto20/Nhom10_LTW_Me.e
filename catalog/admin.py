from django.contrib import admin

from .models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

admin.site.register(ThietBi)
admin.site.register(May)
admin.site.register(GoiThue)
admin.site.register(GiaThue)
admin.site.register(MaGiamGia)
admin.site.register(LoaiThietBi)

from django.contrib import admin

from .models import AnhSuCo, BaoTri, ChiTietDonThue, DonThue, GiaoDich, KiemTraThietBi, PhanBoMay, SuCo, ThongBao

class SoTheoDoiAdmin(admin.ModelAdmin):
    """Tra cứu ở admin; ghi nghiệp vụ qua các màn hình có kiểm tra và giao dịch DB."""
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (DonThue, ChiTietDonThue, PhanBoMay, GiaoDich, KiemTraThietBi, SuCo, AnhSuCo, BaoTri, ThongBao):
    admin.site.register(model, SoTheoDoiAdmin)

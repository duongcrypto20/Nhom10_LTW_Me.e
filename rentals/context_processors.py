"""Context processor: thêm số thông báo chưa đọc và thông tin cửa hàng vào mọi template."""
from django.conf import settings


def thong_bao(request):
    """Đưa số thông báo chưa đọc và thông tin cửa hàng vào mọi template."""
    so_chua_doc = 0
    if request.user.is_authenticated:
        so_chua_doc = request.user.cac_thong_bao.filter(da_doc=False).count()
    return {
        'so_thong_bao_chua_doc': so_chua_doc,
        'cua_hang': settings.CUA_HANG,
    }

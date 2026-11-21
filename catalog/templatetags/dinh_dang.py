"""
Các bộ lọc (filter) định dạng dùng trong template.

Cách dùng trong template:
    {% load dinh_dang %}
    {{ don.tien_thue|tien }}          -> 160.000đ
    {{ thiet_bi.thong_so|bo_ky_tu_trang_tri }}
"""
from django import template

register = template.Library()


@register.filter
def tien(gia_tri):
    """Hiển thị số tiền kiểu Việt Nam: 160000 -> 160.000đ"""
    try:
        so = int(gia_tri)
    except (TypeError, ValueError):
        return ''
    return f'{so:,}'.replace(',', '.') + 'đ'


@register.filter
def bo_ky_tu_trang_tri(gia_tri):
    """Đổi các ký tự trang trí (· × …) sang dấu phẩy, chữ x cho dễ đọc."""
    if gia_tri is None:
        return ''
    van_ban = str(gia_tri)
    for cu, moi in ((' · ', ', '), (' × ', ' x '), ('…', '')):
        van_ban = van_ban.replace(cu, moi)
    return van_ban

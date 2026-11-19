"""Các bộ lọc (filter) định dạng dùng trong template."""
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
def lay(tu_dien, khoa):
    """Lấy giá trị trong dict theo khóa: {{ bang_gia|lay:goi.id }}"""
    if tu_dien is None:
        return ''
    return tu_dien.get(khoa, '')

"""Tính tổ hợp các gói đang cung cấp có tổng giá thấp nhất đủ thời lượng."""
import math
from collections import Counter
from django.core.exceptions import ValidationError
from .models import GiaThue
from catalog.templatetags.dinh_dang import tien


def bao_gia(thiet_bi, goi, gio_nhan, gio_tra):
    if not goi.tuy_chinh:
        try:
            gia = GiaThue.objects.get(thiet_bi=thiet_bi, goi_thue=goi)
        except GiaThue.DoesNotExist:
            raise ValidationError(f'{thiet_bi.ten}: chưa có giá cho gói {goi.ten}.')
        return gia.gia, f'1 × {goi.ten}: {tien(gia.gia)}'
    so_gio = math.ceil((gio_tra - gio_nhan).total_seconds() / 3600)
    if not 1 <= so_gio <= min(goi.so_gio_toi_da, 720):
        raise ValidationError('Thời gian tùy chỉnh phải lớn hơn 0 và không vượt quá giới hạn của gói (tối đa 30 ngày).')
    ds_gia = list(GiaThue.objects.filter(thiet_bi=thiet_bi, goi_thue__dang_cung_cap=True,
        goi_thue__tuy_chinh=False, goi_thue__so_gio_toi_da__gt=0).select_related('goi_thue').order_by('pk'))
    if not ds_gia:
        raise ValidationError(f'{thiet_bi.ten}: cần ít nhất một gói có giá để tính thời gian tùy chỉnh.')
    chi_phi, lua_chon = [0] * (so_gio + 1), [None] * (so_gio + 1)
    for gio in range(1, so_gio + 1):
        chi_phi[gio], lua_chon[gio] = min((chi_phi[max(0, gio - gia.goi_thue.so_gio_toi_da)] + gia.gia, index)
                                      for index, gia in enumerate(ds_gia))
    dem, con = Counter(), so_gio
    while con > 0:
        index = lua_chon[con]
        dem[index] += 1
        con = max(0, con - ds_gia[index].goi_thue.so_gio_toi_da)
    cach = '; '.join(f'{sl} × {ds_gia[i].goi_thue.ten} ({tien(ds_gia[i].gia)}/gói)' for i, sl in dem.items())
    return chi_phi[so_gio], f'Tùy chỉnh {so_gio} giờ (làm tròn lên). Giá thấp nhất đủ thời lượng: {cach}.'

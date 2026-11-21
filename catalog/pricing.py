"""
Tính giá thuê (UC-3.4).

    Gói cố định  : lấy giá trong bảng GiaThue.
    Gói tùy chỉnh: khách tự chọn số giờ, hệ thống ghép các gói có sẵn sao cho
                   đủ thời lượng và rẻ nhất (bài toán quy hoạch động "đổi tiền").
"""
import math
from collections import Counter

from django.core.exceptions import ValidationError

from .models import GiaThue
from .templatetags.dinh_dang import tien

SO_GIO_TOI_DA_TUY_CHINH = 720  # 30 ngày


def bao_gia(thiet_bi, goi, gio_nhan, gio_tra):
    """
    Trả về (số tiền, cách tính) của một máy theo gói và thời gian thuê.

    Giá luôn lấy từ database, không đọc giá do trình duyệt gửi lên.
    """
    if not goi.tuy_chinh:
        return bao_gia_goi_co_dinh(thiet_bi, goi)
    return bao_gia_tuy_chinh(thiet_bi, goi, gio_nhan, gio_tra)


def bao_gia_goi_co_dinh(thiet_bi, goi):
    """Gói cố định: tra bảng giá."""
    try:
        gia = GiaThue.objects.get(thiet_bi=thiet_bi, goi_thue=goi)
    except GiaThue.DoesNotExist:
        raise ValidationError(f'{thiet_bi.ten}: chưa có giá cho gói {goi.ten}.')
    return gia.gia, f'{goi.ten}, số lượng 1: {tien(gia.gia)}'


def bao_gia_tuy_chinh(thiet_bi, goi, gio_nhan, gio_tra):
    """Gói tùy chỉnh: tìm tổ hợp các gói rẻ nhất mà tổng thời lượng đủ số giờ thuê."""
    # Bước 1: số giờ thuê (làm tròn lên) và kiểm tra giới hạn
    so_gio = math.ceil((gio_tra - gio_nhan).total_seconds() / 3600)
    if not 1 <= so_gio <= min(goi.so_gio_toi_da, SO_GIO_TOI_DA_TUY_CHINH):
        raise ValidationError('Thời gian tùy chỉnh phải lớn hơn 0 và không quá 30 ngày.')

    # Bước 2: các gói cố định đang có giá của máy này
    ds_gia = list(
        GiaThue.objects
        .filter(
            thiet_bi=thiet_bi,
            goi_thue__dang_cung_cap=True,
            goi_thue__tuy_chinh=False,
            goi_thue__so_gio_toi_da__gt=0,
        )
        .select_related('goi_thue')
        .order_by('pk')
    )
    if not ds_gia:
        raise ValidationError(f'{thiet_bi.ten}: cần ít nhất một gói có giá để tính thời gian tùy chỉnh.')

    # Bước 3: quy hoạch động
    #   chi_phi[g]  = số tiền ít nhất để thuê đủ g giờ
    #   lua_chon[g] = gói được chọn cuối cùng để đạt chi_phi[g]
    chi_phi = [0] * (so_gio + 1)
    lua_chon = [None] * (so_gio + 1)
    for gio in range(1, so_gio + 1):
        tot_nhat = None
        for vi_tri, gia in enumerate(ds_gia):
            gio_con_thieu = max(0, gio - gia.goi_thue.so_gio_toi_da)
            tong = chi_phi[gio_con_thieu] + gia.gia
            if tot_nhat is None or tong < tot_nhat:
                tot_nhat = tong
                lua_chon[gio] = vi_tri
        chi_phi[gio] = tot_nhat

    # Bước 4: đi ngược bảng để biết đã dùng những gói nào, giải thích cho khách
    so_lan_dung = Counter()
    gio_con_lai = so_gio
    while gio_con_lai > 0:
        vi_tri = lua_chon[gio_con_lai]
        so_lan_dung[vi_tri] += 1
        gio_con_lai = max(0, gio_con_lai - ds_gia[vi_tri].goi_thue.so_gio_toi_da)

    cac_goi = []
    for vi_tri, so_luong in so_lan_dung.items():
        gia = ds_gia[vi_tri]
        cac_goi.append(f'{gia.goi_thue.ten}, số lượng {so_luong} ({tien(gia.gia)}/gói)')

    cach_tinh = (
        f'Tùy chỉnh {so_gio} giờ (làm tròn lên). '
        f'Giá thấp nhất đủ thời lượng: {"; ".join(cac_goi)}.'
    )
    return chi_phi[so_gio], cach_tinh

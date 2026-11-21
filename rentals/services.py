"""
Nghiệp vụ của đơn thuê và tiền cọc.

Mỗi hàm ở đây là một bước trong quy trình TO-BE:

    1. Khách đặt thuê       : kiem_tra_ban_nhap(), luu_yeu_cau()
    2. Nhân viên xử lý đơn  : xac_nhan_lich(), huy_yeu_cau(), phan_bo_lai()
    3. Khách cọc lịch online: dat_coc_online()
    4. Khách nhận máy       : thu_coc_khi_nhan_may()
    5. Khách trả máy        : hoan_coc_khi_tra_may()
    6. Sự cố máy            : ghi_nhan_su_co()

Hàm nào thay đổi đơn, máy và tiền cùng lúc đều chạy trong transaction.atomic:
nếu một bước bị lỗi thì toàn bộ thay đổi được hủy, không có chuyện thu tiền mà máy chưa giữ.
"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import GiaThue, GoiThue, MaGiamGia, May, ThietBi
from catalog.pricing import bao_gia
from catalog.templatetags.dinh_dang import tien

from .models import AnhSuCo, ChiTietDonThue, DonThue, GiaoDich, PhanBoMay, SuCo
from .utils import cac_may_trong, gui_thong_bao, tinh_phi_tra_tre


# ===========================================================================
# HÀM DÙNG CHUNG
# ===========================================================================

def khoa_don(pk):
    """
    Đọc đơn và khóa lại để hai người không xử lý cùng một đơn một lúc.

    SQLite không hỗ trợ select_for_update, nên cập nhật "giả" một trường để
    giữ khóa ghi tới hết transaction. Với PostgreSQL thì select_for_update là đủ.
    """
    DonThue.objects.filter(pk=pk).update(trang_thai=F('trang_thai'))
    return DonThue.objects.select_for_update().get(pk=pk)


def ghi_giao_dich(don, loai, so_tien, phuong_thuc, nguoi_ghi=None):
    """Ghi một dòng vào sổ giao dịch tiền của đơn."""
    return GiaoDich.objects.create(
        don=don,
        loai=loai,
        so_tien=so_tien,
        phuong_thuc=phuong_thuc,
        nguoi_xac_nhan=nguoi_ghi,
    )


def bao_cho_nhan_vien(noi_dung, don, tieu_de):
    """Gửi thông báo cho tất cả nhân viên và chủ cửa hàng đang hoạt động."""
    User = get_user_model()
    ds_nhan_vien = User.objects.filter(
        vai_tro__in=[User.NHAN_VIEN, User.CHU_CUA_HANG],
        is_active=True,
    )
    for nhan_vien in ds_nhan_vien:
        gui_thong_bao(nhan_vien, noi_dung, don, tieu_de=tieu_de)


# ===========================================================================
# 1. KHÁCH ĐẶT THUÊ (UC-1.1, UC-1.2)
# ===========================================================================

def doc_goi_va_thoi_gian(tam):
    """Đọc gói thuê, giờ nhận, giờ trả trong bản nháp và kiểm tra hợp lệ."""
    goi = GoiThue.objects.get(pk=tam['goi_thue_id'], dang_cung_cap=True)
    gio_nhan = datetime.fromisoformat(tam['gio_nhan'])
    gio_tra = datetime.fromisoformat(tam['gio_tra'])

    if timezone.is_naive(gio_nhan) or timezone.is_naive(gio_tra):
        raise ValueError('Thiếu múi giờ')

    so_giay = (gio_tra - gio_nhan).total_seconds()
    if gio_nhan <= timezone.now() or not 0 < so_giay <= goi.so_gio_toi_da * 3600:
        raise ValidationError('Giờ nhận đã qua hoặc thời lượng không phù hợp với gói. Vui lòng chọn lại.')
    return goi, gio_nhan, gio_tra


def lap_cac_dong(tam, goi, gio_nhan, gio_tra):
    """Tính giá từng dòng máy trong bản nháp và kiểm tra còn đủ máy trống."""
    cac_dong = []
    da_chon = set()

    for muc in tam['cac_muc']:
        thiet_bi = ThietBi.objects.get(pk=muc['thiet_bi_id'], ngung_cung_cap=False)
        so_luong = int(muc['so_luong'])

        # Mỗi dòng máy chỉ xuất hiện một lần, số lượng từ 1 đến 20
        if thiet_bi.pk in da_chon or not 1 <= so_luong <= 20:
            raise ValidationError('Số lượng thiết bị không hợp lệ.')
        da_chon.add(thiet_bi.pk)

        # Giá luôn tính lại từ database, không tin giá do trình duyệt gửi lên
        don_gia, cach_tinh = bao_gia(thiet_bi, goi, gio_nhan, gio_tra)

        if cac_may_trong(thiet_bi, gio_nhan, gio_tra).count() < so_luong:
            raise ValidationError(f'{thiet_bi.ten}: không đủ máy trống trong thời gian đã chọn.')

        cac_dong.append({
            'thiet_bi': thiet_bi,
            'so_luong': so_luong,
            'don_gia': don_gia,
            'thanh_tien': so_luong * don_gia,
            'cach_tinh_gia': cach_tinh,
        })

    if not cac_dong:
        raise ValidationError('Vui lòng chọn ít nhất một thiết bị.')
    return cac_dong


def tim_ma_giam_gia(tam, ma_da_dung=''):
    """Tìm mã giảm giá khách nhập. Mã đã dùng cho chính đơn này thì vẫn được giữ."""
    ma = tam.get('ma_giam_gia', '').upper().strip()
    if not ma:
        return None

    voucher = MaGiamGia.objects.filter(ma=ma).first()
    if not voucher or (ma != ma_da_dung and not voucher.co_hieu_luc()):
        raise ValidationError('Mã giảm giá hết hạn, hết lượt hoặc đã ngừng áp dụng.')
    return voucher


def kiem_tra_ban_nhap(tam, ma_da_dung=''):
    """
    Kiểm tra bản nháp đặt thuê (lưu trong session) và lập báo giá.

    Trả về dict gồm: gói thuê, giờ nhận, giờ trả, các dòng máy,
    tổng tiền thuê, tổng tiền cọc, mã giảm giá và số tiền được giảm.
    """
    try:
        goi, gio_nhan, gio_tra = doc_goi_va_thoi_gian(tam)
        cac_dong = lap_cac_dong(tam, goi, gio_nhan, gio_tra)
        voucher = tim_ma_giam_gia(tam, ma_da_dung)
    except (KeyError, TypeError, ValueError,
            ThietBi.DoesNotExist, GoiThue.DoesNotExist, GiaThue.DoesNotExist):
        raise ValidationError('Thiết bị, gói thuê hoặc bảng giá đã thay đổi. Vui lòng chọn lại.')

    tien_thue = sum(dong['thanh_tien'] for dong in cac_dong)
    tien_coc = sum(dong['thiet_bi'].tien_coc * dong['so_luong'] for dong in cac_dong)
    giam_gia = voucher.tinh_giam(tien_thue) if voucher else 0

    return {
        'goi_thue': goi,
        'gio_nhan': gio_nhan,
        'gio_tra': gio_tra,
        'cac_dong': cac_dong,
        'tien_thue': tien_thue,
        'tien_coc': tien_coc,
        'voucher': voucher,
        'giam_gia': giam_gia,
    }


@transaction.atomic
def luu_yeu_cau(user, tam, don_pk=None):
    """
    Lưu đơn thuê từ bản nháp.

    don_pk = None : tạo đơn mới.
    don_pk có giá trị: khách sửa lại đơn đang ở trạng thái "Cần điều chỉnh".
    """
    # Bước 1: chống bấm gửi hai lần: cùng mã gửi thì trả về đơn đã tạo
    if not don_pk and tam.get('ma_gui'):
        da_gui = DonThue.objects.filter(ma_gui=tam['ma_gui'], khach_hang=user).first()
        if da_gui:
            return da_gui

    # Bước 2: nếu sửa đơn thì chỉ cho sửa đơn của mình đang cần điều chỉnh
    don = khoa_don(don_pk) if don_pk else None
    if don and (don.khach_hang_id != user.pk or don.trang_thai != DonThue.CAN_DIEU_CHINH):
        raise ValidationError('Không thể điều chỉnh đơn này.')

    # Bước 3: tính lại giá và kiểm tra máy trống
    ma_cu = don.ma_giam_gia if don else ''
    bao_gia_don = kiem_tra_ban_nhap(tam, ma_cu)
    voucher = bao_gia_don['voucher']

    # Bước 4: trừ lượt mã giảm giá mới, trả lượt cho mã cũ nếu khách đổi mã
    if voucher and voucher.ma != ma_cu:
        da_tru = MaGiamGia.objects.filter(pk=voucher.pk, so_luot__gt=0).update(so_luot=F('so_luot') - 1)
        if not da_tru:
            raise ValidationError('Mã giảm giá vừa hết lượt. Vui lòng chọn lại.')
    if ma_cu and ma_cu != (voucher.ma if voucher else ''):
        MaGiamGia.objects.filter(ma=ma_cu).update(so_luot=F('so_luot') + 1)

    # Bước 5: lưu thông tin đơn
    if don is None:
        don = DonThue(khach_hang=user, ma_gui=tam.get('ma_gui'))
    don.thiet_bi = bao_gia_don['cac_dong'][0]['thiet_bi']
    don.goi_thue = bao_gia_don['goi_thue']
    don.gio_nhan = bao_gia_don['gio_nhan']
    don.gio_tra = bao_gia_don['gio_tra']
    don.tien_thue = bao_gia_don['tien_thue']
    don.giam_gia = bao_gia_don['giam_gia']
    don.tien_coc = bao_gia_don['tien_coc']
    don.ma_giam_gia = voucher.ma if voucher else ''
    don.ghi_chu = tam.get('ghi_chu', '')
    don.trang_thai = DonThue.CHO_XU_LY
    don.ly_do = ''
    don.save()

    # Bước 6: lưu lại các dòng máy (xóa dòng cũ nếu là sửa đơn)
    don.cac_chi_tiet.all().delete()
    for dong in bao_gia_don['cac_dong']:
        ChiTietDonThue.objects.create(
            don=don,
            thiet_bi=dong['thiet_bi'],
            so_luong=dong['so_luong'],
            don_gia=dong['don_gia'],
            tien_coc_don_vi=dong['thiet_bi'].tien_coc,
            cach_tinh_gia=dong['cach_tinh_gia'],
        )

    gui_thong_bao(
        user,
        f'Đã tạo đơn {don.ma}. Cọc lịch {tien(don.tien_coc_giu_lich)} để giữ máy; '
        'khoản này được tính vào tiền cọc máy.',
        don,
    )
    return don


# ===========================================================================
# 2. NHÂN VIÊN XỬ LÝ ĐƠN (UC-1.4)
# ===========================================================================

def phan_bo_may(don):
    """
    Chọn máy trống (số sê-ri) cho từng dòng của đơn và giữ máy.

    Hàm này được gọi bên trong một transaction (xác nhận lịch hoặc đặt cọc).
    """
    if don.gio_nhan <= timezone.now():
        raise ValidationError('Giờ nhận máy đã qua. Vui lòng chọn lại thời gian thuê.')

    ds_phan_bo = []
    for dong in don.cac_chi_tiet.select_related('thiet_bi'):
        if dong.thiet_bi.ngung_cung_cap:
            raise ValidationError(f'{dong.thiet_bi.ten} đã ngừng cung cấp.')

        may_trong = list(cac_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don)[:dong.so_luong])
        if len(may_trong) != dong.so_luong:
            raise ValidationError(f'{dong.thiet_bi.ten}: không còn đủ máy trống trong thời gian đã chọn.')

        for may in may_trong:
            ds_phan_bo.append(PhanBoMay(chi_tiet=dong, may=may))

    if not ds_phan_bo:
        raise ValidationError('Đơn chưa có chi tiết thiết bị.')

    PhanBoMay.objects.bulk_create(ds_phan_bo)
    don.trang_thai = DonThue.DA_XAC_NHAN
    don.save(update_fields=['trang_thai'])


@transaction.atomic
def xac_nhan_lich(pk):
    """Nhân viên xác nhận đơn khách chưa cọc online: giữ máy, khách cọc tại quầy khi nhận máy."""
    don = khoa_don(pk)
    if don.trang_thai != DonThue.CHO_XU_LY:
        raise ValidationError('Yêu cầu đã được xử lý trước đó.')

    phan_bo_may(don)
    gui_thong_bao(
        don.khach_hang,
        f'{don.ma} đã được xác nhận. Bạn có thể cọc lịch online {tien(don.tien_coc_giu_lich)}; '
        'phần cọc máy còn lại thu khi nhận máy.',
        don,
    )
    return don


@transaction.atomic
def huy_yeu_cau(pk, ly_do, khach_hang=None, dieu_chinh=False):
    """
    Hủy đơn, hoặc yêu cầu khách điều chỉnh (dieu_chinh=True).

    khach_hang: truyền vào khi chính khách tự hủy, để kiểm tra đúng chủ đơn.
    """
    don = khoa_don(pk)
    if khach_hang and don.khach_hang_id != khach_hang.pk:
        raise ValidationError('Không có quyền xử lý đơn thuê này.')
    if not don.co_the_huy:
        raise ValidationError('Đơn đã được xử lý, không thể thực hiện thao tác này.')
    if dieu_chinh and not ly_do.strip():
        raise ValidationError('Vui lòng nhập lý do hoặc gợi ý cho khách.')

    # Hủy hẳn thì trả lại lượt mã giảm giá
    if not dieu_chinh and don.ma_giam_gia:
        MaGiamGia.objects.filter(ma=don.ma_giam_gia).update(so_luot=F('so_luot') + 1)

    # Bỏ các máy đang giữ để máy trở lại lịch trống
    PhanBoMay.objects.filter(chi_tiet__don=don).delete()

    don.trang_thai = DonThue.CAN_DIEU_CHINH if dieu_chinh else DonThue.DA_HUY
    don.ly_do = ly_do
    don.save(update_fields=['trang_thai', 'ly_do'])
    gui_thong_bao(don.khach_hang, f'{don.ma}: {don.get_trang_thai_display()}. {ly_do}', don)


@transaction.atomic
def phan_bo_lai(pk):
    """Đổi sang máy khác cùng dòng cho đơn đã xác nhận (ví dụ máy đang giữ bị hỏng)."""
    don = khoa_don(pk)
    if don.trang_thai != DonThue.DA_XAC_NHAN:
        raise ValidationError('Chỉ đổi máy cho đơn đã xác nhận và chưa giao.')

    ds_moi = []
    for dong in don.cac_chi_tiet.select_related('thiet_bi'):
        may_trong = list(cac_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don)[:dong.so_luong])
        if len(may_trong) != dong.so_luong:
            raise ValidationError(f'{dong.thiet_bi.ten}: chưa đủ máy thay thế. Phân bổ cũ được giữ nguyên.')
        for may in may_trong:
            ds_moi.append(PhanBoMay(chi_tiet=dong, may=may))

    PhanBoMay.objects.filter(chi_tiet__don=don).delete()
    PhanBoMay.objects.bulk_create(ds_moi)
    gui_thong_bao(
        don.khach_hang,
        f'{don.ma}: cửa hàng đã đổi số sê-ri máy được giữ. Dòng máy và giá thuê giữ nguyên.',
        don,
    )


# ===========================================================================
# 3. KHÁCH CỌC LỊCH ONLINE (TO-BE bước 6)
# ===========================================================================

def kiem_tra_may_da_giu(don):
    """
    Kiểm tra các máy đang giữ cho đơn: đủ số lượng, đúng dòng máy và vẫn dùng được.

    Trả về danh sách PhanBoMay của đơn.
    """
    cac_phan_bo = list(PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may', 'chi_tiet'))
    if not cac_phan_bo:
        raise ValidationError('Đơn chưa được giữ máy. Vui lòng kiểm tra lại lịch.')

    for dong in don.cac_chi_tiet.select_related('thiet_bi'):
        if dong.thiet_bi.ngung_cung_cap:
            raise ValidationError(f'{dong.thiet_bi.ten} đã ngừng cung cấp.')

        may_cua_dong = [pb for pb in cac_phan_bo if pb.chi_tiet_id == dong.pk]
        if len(may_cua_dong) != dong.so_luong:
            raise ValidationError('Số máy đang giữ chưa khớp số lượng đặt thuê. Vui lòng đổi máy.')

        # Máy có thể vừa hỏng hoặc bị một đơn trả trễ giữ lại
        ma_may_trong = set(
            cac_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don).values_list('pk', flat=True)
        )
        for phan_bo in may_cua_dong:
            if phan_bo.may_id not in ma_may_trong:
                raise ValidationError(
                    f'Máy {phan_bo.may.so_seri} không còn sẵn sàng. Vui lòng đổi máy khác trước.'
                )
    return cac_phan_bo


@transaction.atomic
def dat_coc_online(pk, khach_hang):
    """
    Khách cọc lịch 50.000đ online để giữ máy.

    Cổng thanh toán là mô phỏng: khách bấm thanh toán thì ghi nhận thành công ngay.
    Muốn dùng cổng thật (VNPay, MoMo) thì gọi hàm này khi cổng báo thanh toán thành công.
    """
    don = khoa_don(pk)

    # Kiểm tra điều kiện được cọc
    if don.khach_hang_id != khach_hang.pk:
        raise ValidationError('Không có quyền đặt cọc cho đơn thuê này.')
    if not don.cho_dat_coc:
        raise ValidationError('Đơn không ở trạng thái chờ đặt cọc.')
    if don.gio_nhan <= timezone.now():
        raise ValidationError('Giờ nhận máy đã qua. Vui lòng liên hệ cửa hàng trước khi cọc.')

    # Đơn mới: giữ máy ngay khi cọc. Đơn đã được giữ: kiểm tra lại máy còn dùng được
    if don.trang_thai == DonThue.CHO_XU_LY:
        phan_bo_may(don)
    else:
        kiem_tra_may_da_giu(don)

    # Ghi nhận tiền cọc lịch
    so_tien = min(don.tien_coc_giu_lich, don.tien_coc_con_lai)
    giao_dich = ghi_giao_dich(don, GiaoDich.DAT_COC, so_tien, 'online')
    don.trang_thai_coc = DonThue.DA_THU
    don.hinh_thuc_coc = 'online'
    don.save(update_fields=['trang_thai_coc', 'hinh_thuc_coc'])

    # Báo cho khách và nhân viên
    con_lai = tien(don.tien_coc_con_lai)
    gui_thong_bao(
        don.khach_hang,
        f'{don.ma}: cọc lịch thành công {tien(so_tien)}. Đã giữ máy; '
        f'cọc máy còn lại {con_lai} thu khi nhận máy.',
        don,
        tieu_de='Đặt cọc thành công',
    )
    bao_cho_nhan_vien(
        f'{don.ma}: khách đã cọc lịch {tien(so_tien)}, hệ thống đã giữ máy. '
        f'Thu thêm cọc máy {con_lai} khi khách nhận máy.',
        don,
        tieu_de='Khách đã đặt cọc',
    )
    return giao_dich


# ===========================================================================
# 4. KHÁCH NHẬN MÁY: THU COC VÀ TIỀN THUÊ
# ===========================================================================

@transaction.atomic
def thu_coc_khi_nhan_may(pk, nhan_vien, phuong_thuc, gio_giao=None):
    """
    Khách đến nhận máy: nhân viên thu tiền thuê và phần cọc máy còn thiếu.

    Sau bước này: đơn chuyển sang "Đang thuê", các máy chuyển sang "Đang thuê".
    """
    # Giờ giao làm tròn xuống tới phút, khớp với ô nhập giờ trả (không có giây)
    gio_giao = gio_giao or timezone.now().replace(second=0, microsecond=0)
    don = khoa_don(pk)

    if don.trang_thai != DonThue.DA_XAC_NHAN:
        raise ValidationError('Đơn đã giao hoặc không ở trạng thái chờ nhận máy.')
    if gio_giao > timezone.now() or gio_giao >= don.gio_tra:
        raise ValidationError('Giờ giao phải không ở tương lai và phải trước hạn trả máy.')

    # Kiểm tra từng máy đã giữ còn sẵn sàng
    cac_phan_bo = list(PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may'))
    if not cac_phan_bo:
        raise ValidationError('Đơn chưa được giữ máy. Vui lòng đổi máy trước khi giao.')
    for phan_bo in cac_phan_bo:
        if phan_bo.may.tinh_trang != May.SAN_SANG:
            raise ValidationError(f'Máy {phan_bo.may.so_seri} chưa sẵn sàng để giao.')

    # Ghi tiền: phần cọc còn thiếu và tiền thuê
    coc_con_lai = don.tien_coc_con_lai
    if coc_con_lai:
        ghi_giao_dich(don, GiaoDich.DAT_COC, coc_con_lai, phuong_thuc, nhan_vien)
    ghi_giao_dich(don, GiaoDich.THANH_TOAN, don.tong_thanh_toan, phuong_thuc, nhan_vien)

    # Cập nhật đơn và máy
    if don.trang_thai_coc == DonThue.CHUA_THU:
        don.hinh_thuc_coc = phuong_thuc
    don.trang_thai_coc = DonThue.DA_THU
    don.giao_thuc_te = gio_giao
    don.trang_thai = DonThue.DANG_THUE
    don.save()
    May.objects.filter(pk__in=[pb.may_id for pb in cac_phan_bo]).update(tinh_trang=May.DANG_THUE)

    han_tra = timezone.localtime(don.gio_tra)
    gui_thong_bao(don.khach_hang, f'{don.ma}: đã nhận máy. Nhớ trả máy trước {han_tra:%H:%M %d/%m}.', don)


# ===========================================================================
# 5. KHÁCH TRẢ MÁY: HOÀN CỌC
# ===========================================================================

@transaction.atomic
def hoan_coc_khi_tra_may(pk, nhan_vien, tra_thuc_te, hinh_thuc_tra, phuong_thuc,
                         may_hu_hong=(), mo_ta_hu_hong='', khau_tru_den_bu=0):
    """
    Khách trả máy: tính phụ thu trả trễ, khấu trừ đền bù (nếu máy hỏng) và hoàn cọc.

    Tiền hoàn = tiền cọc - phụ thu trả trễ - khấu trừ đền bù (không âm).
    Nếu phụ thu + đền bù lớn hơn tiền cọc thì thu thêm phần chênh lệch.
    Máy bình thường về "Sẵn sàng", máy hư hỏng chuyển sang "Bảo trì".
    """
    don = khoa_don(pk)

    # Kiểm tra điều kiện
    if don.trang_thai != DonThue.DANG_THUE or don.trang_thai_coc != DonThue.DA_THU:
        raise ValidationError('Chỉ hoàn cọc cho đơn đang thuê và đã thu cọc.')
    if tra_thuc_te > timezone.now() or (don.giao_thuc_te and tra_thuc_te < don.giao_thuc_te):
        raise ValidationError('Giờ trả phải sau giờ giao và không ở tương lai.')
    if khau_tru_den_bu and not may_hu_hong:
        raise ValidationError('Cần chọn máy hư hỏng trước khi khấu trừ đền bù.')
    if may_hu_hong and not mo_ta_hu_hong.strip():
        raise ValidationError('Vui lòng mô tả tình trạng hư hỏng của máy.')

    # Tính tiền
    don.phu_thu_tra_tre = tinh_phi_tra_tre(don.gio_tra, tra_thuc_te)
    don.khau_tru_den_bu = khau_tru_den_bu
    don.hoan_lai = max(don.tien_coc - don.phu_thu_tra_tre - khau_tru_den_bu, 0)

    if don.hoan_lai == don.tien_coc:
        don.trang_thai_coc = DonThue.DA_HOAN
    elif don.hoan_lai == 0:
        don.trang_thai_coc = DonThue.KHAU_TRU_TOAN_BO
    else:
        don.trang_thai_coc = DonThue.HOAN_MOT_PHAN

    # Cập nhật tình trạng từng máy
    ma_may_hong = {may.pk for may in may_hu_hong}
    ghi_chu_may = []
    for phan_bo in PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may'):
        may = phan_bo.may
        if may.pk in ma_may_hong:
            may.tinh_trang = May.BAO_TRI
            ghi_chu_may.append(f'{may.so_seri}: hư hỏng')
        else:
            may.tinh_trang = May.SAN_SANG
            ghi_chu_may.append(f'{may.so_seri}: bình thường')
        may.save(update_fields=['tinh_trang'])

    # Lưu đơn
    don.tra_thuc_te = tra_thuc_te
    don.hinh_thuc_tra = hinh_thuc_tra
    don.tinh_trang_khi_tra = '; '.join(ghi_chu_may)
    if mo_ta_hu_hong.strip():
        don.tinh_trang_khi_tra += f'. Mô tả: {mo_ta_hu_hong.strip()}'
    don.trang_thai = DonThue.HOAN_TAT
    don.save()

    # Ghi tiền hoàn cọc và tiền thu thêm (nếu có)
    if don.hoan_lai:
        ghi_giao_dich(don, GiaoDich.HOAN_COC, don.hoan_lai, phuong_thuc, nhan_vien)
    if don.can_thu_them:
        ghi_giao_dich(don, GiaoDich.PHU_THU, don.can_thu_them, phuong_thuc, nhan_vien)

    loi_nhan = f'{don.ma} đã hoàn tất. Hoàn cọc {tien(don.hoan_lai)}'
    if don.phu_thu_tra_tre:
        loi_nhan += f', phụ thu trả trễ {tien(don.phu_thu_tra_tre)}'
    gui_thong_bao(don.khach_hang, loi_nhan + '. Mời bạn gửi đánh giá cho đơn thuê.', don)


# ===========================================================================
# 6. SỰ CỐ MÁY
# ===========================================================================

@transaction.atomic
def ghi_nhan_su_co(pk, nhan_vien, may, muc_do, mo_ta, ds_anh):
    """
    Nhân viên ghi nhận sự cố cho một máy của đơn, kèm ảnh chụp chỗ hỏng.

    Lỗi nặng: máy chuyển sang "Bảo trì" ngay nếu máy đang ở cửa hàng.
    Nếu khách đang cầm máy thì máy chuyển "Bảo trì" khi nhân viên hoàn cọc.
    """
    don = khoa_don(pk)
    if don.trang_thai not in (DonThue.DA_XAC_NHAN, DonThue.DANG_THUE, DonThue.HOAN_TAT):
        raise ValidationError('Chỉ ghi nhận sự cố cho đơn đã giữ máy, đang thuê hoặc vừa hoàn tất.')
    if not PhanBoMay.objects.filter(chi_tiet__don=don, may=may).exists():
        raise ValidationError('Máy này không thuộc đơn thuê.')

    # Lưu sự cố và từng ảnh
    su_co = SuCo.objects.create(don=don, may=may, muc_do=muc_do, mo_ta=mo_ta, nhan_vien=nhan_vien)
    for anh in ds_anh:
        AnhSuCo.objects.create(su_co=su_co, anh=anh)

    # Lỗi nặng và máy không ở trong tay khách: ngừng cho thuê máy này
    if muc_do == SuCo.NANG and may.tinh_trang != May.DANG_THUE:
        may.tinh_trang = May.BAO_TRI
        may.save(update_fields=['tinh_trang'])

    gui_thong_bao(
        don.khach_hang,
        f'{don.ma}: cửa hàng đã ghi nhận sự cố ({su_co.get_muc_do_display()}) của máy {may.so_seri}.',
        don,
        tieu_de='Sự cố thiết bị',
    )
    return su_co


def ma_may_co_su_co_nang(don):
    """Id các máy của đơn có sự cố nặng chưa xử lý, dùng để chọn sẵn ở trang hoàn cọc."""
    return list(
        SuCo.objects
        .filter(don=don, muc_do=SuCo.NANG, trang_thai=SuCo.CHO_XU_LY)
        .values_list('may_id', flat=True)
    )

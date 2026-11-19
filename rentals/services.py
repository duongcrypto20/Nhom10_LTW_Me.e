"""Các thay đổi đơn, lịch, máy và tiền luôn được lưu trong cùng giao dịch DB."""
import uuid
from datetime import datetime
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from catalog.models import GiaThue, GoiThue, MaGiamGia, May, ThietBi
from catalog.pricing import bao_gia
from .models import AnhSuCo, ChiTietDonThue, DonThue, GiaoDich, KiemTraThietBi, PhanBoMay, SuCo
from .utils import cac_may_trong, gui_thong_bao, tinh_phi_tra_tre
from catalog.templatetags.dinh_dang import tien


def khoa_don(pk):
    # UPDATE also obtains SQLite's write lock; FOR UPDATE covers PostgreSQL.
    DonThue.objects.filter(pk=pk).update(trang_thai=F('trang_thai'))
    return DonThue.objects.select_for_update().get(pk=pk)


def kiem_tra_ban_nhap(tam, voucher_da_dung=''):
    try:
        goi = GoiThue.objects.get(pk=tam['goi_thue_id'], dang_cung_cap=True)
        nhan, tra = datetime.fromisoformat(tam['gio_nhan']), datetime.fromisoformat(tam['gio_tra'])
        if timezone.is_naive(nhan) or timezone.is_naive(tra):
            raise ValueError
        if nhan <= timezone.now() or not 0 < (tra - nhan).total_seconds() <= goi.so_gio_toi_da * 3600:
            raise ValidationError('Giờ nhận đã qua hoặc thời lượng không phù hợp với gói. Vui lòng chọn lại.')
        dong, da_co = [], set()
        for item in tam['cac_muc']:
            tb = ThietBi.objects.get(pk=item['thiet_bi_id'], ngung_cung_cap=False)
            sl = int(item['so_luong'])
            if tb.pk in da_co or not 1 <= sl <= 20:
                raise ValidationError('Số lượng thiết bị không hợp lệ.')
            da_co.add(tb.pk)
            gia, cach_tinh = bao_gia(tb, goi, nhan, tra)
            if cac_may_trong(tb, nhan, tra).count() < sl:
                raise ValidationError(f'{tb.ten}: không đủ máy trống trong thời gian đã chọn.')
            dong.append((tb, sl, gia))
        if not dong:
            raise ValidationError('Vui lòng chọn ít nhất một thiết bị.')
        tong = sum(sl * gia for tb, sl, gia in dong)
        coc = sum(tb.tien_coc * sl for tb, sl, gia in dong)
        voucher = None
        ma = tam.get('ma_giam_gia', '').upper().strip()
        if ma:
            voucher = MaGiamGia.objects.select_for_update().filter(ma=ma).first()
            if not voucher or (ma != voucher_da_dung and not voucher.co_hieu_luc()):
                raise ValidationError('Mã giảm giá hết hạn, hết lượt hoặc đã ngừng áp dụng.')
        return goi, nhan, tra, dong, tong, coc, voucher, voucher.tinh_giam(tong) if voucher else 0
    except (KeyError, TypeError, ValueError, ThietBi.DoesNotExist, GoiThue.DoesNotExist, GiaThue.DoesNotExist):
        raise ValidationError('Thiết bị, gói thuê hoặc bảng giá đã thay đổi. Vui lòng chọn lại.')


@transaction.atomic
def luu_yeu_cau(user, tam, don_pk=None):
    get_user_model().objects.filter(pk=user.pk).update(last_login=F('last_login'))
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if not don_pk and tam.get('ma_gui'):
        da_gui = DonThue.objects.filter(ma_gui=tam['ma_gui'], khach_hang=user).first()
        if da_gui:
            return da_gui
    don = khoa_don(don_pk) if don_pk else None
    if don and (don.khach_hang_id != user.pk or don.trang_thai != DonThue.CAN_DIEU_CHINH):
        raise ValidationError('Không thể điều chỉnh đơn này.')
    ma_cu = don.ma_giam_gia if don else ''
    goi, nhan, tra, dong, tong, coc, voucher, giam = kiem_tra_ban_nhap(tam, ma_cu)
    if voucher and voucher.ma != ma_cu:
        if not MaGiamGia.objects.filter(pk=voucher.pk, so_luot__gt=0).update(so_luot=F('so_luot') - 1):
            raise ValidationError('Mã giảm giá vừa hết lượt. Vui lòng chọn lại.')
    if ma_cu and ma_cu != (voucher.ma if voucher else ''):
        MaGiamGia.objects.filter(ma=ma_cu).update(so_luot=F('so_luot') + 1)
    don = don or DonThue(khach_hang=user)
    if not don_pk:
        don.ma_gui = tam.get('ma_gui')
    don.thiet_bi, don.goi_thue = dong[0][0], goi
    don.gio_nhan, don.gio_tra = nhan, tra
    don.tien_thue, don.giam_gia, don.tien_coc = tong, giam, coc
    don.ma_giam_gia = voucher.ma if voucher else ''
    don.trang_thai, don.ly_do, don.may = DonThue.CHO_XU_LY, '', None
    don.ghi_chu = tam.get('ghi_chu', '')
    don.save()
    don.cac_chi_tiet.all().delete()
    ChiTietDonThue.objects.bulk_create([ChiTietDonThue(don=don, thiet_bi=tb, so_luong=sl,
        don_gia=gia, tien_coc_don_vi=tb.tien_coc,
        cach_tinh_gia=bao_gia(tb, goi, nhan, tra)[1]) for tb, sl, gia in dong])
    gui_thong_bao(user, f'Đã tạo đơn {don.ma}. Cọc lịch {tien(don.tien_coc_giu_lich)} để giữ máy; '
                  'khoản này được tính vào tiền cọc máy.', don)
    return don


def phan_bo_may(don):
    """Chọn máy trống cho từng dòng thiết bị của đơn và giữ máy (gọi bên trong giao dịch DB)."""
    if don.gio_nhan <= timezone.now():
        raise ValidationError('Giờ nhận máy đã qua. Vui lòng chọn lại thời gian thuê.')
    phan_bo = []
    for dong in don.cac_chi_tiet.select_related('thiet_bi'):
        if dong.thiet_bi.ngung_cung_cap:
            raise ValidationError(f'{dong.thiet_bi.ten} đã ngừng cung cấp.')
        ThietBi.objects.select_for_update().get(pk=dong.thiet_bi_id)
        may = list(cac_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don).select_for_update()[:dong.so_luong])
        if len(may) != dong.so_luong:
            raise ValidationError(f'{dong.thiet_bi.ten}: không còn đủ máy trống trong thời gian đã chọn.')
        phan_bo.extend(PhanBoMay(chi_tiet=dong, may=m) for m in may)
    if not phan_bo:
        raise ValidationError('Đơn chưa có chi tiết thiết bị.')
    PhanBoMay.objects.bulk_create(phan_bo)
    don.may, don.trang_thai = phan_bo[0].may, DonThue.DA_XAC_NHAN
    don.save(update_fields=['may', 'trang_thai'])


@transaction.atomic
def xac_nhan_lich(pk):
    """Nhân viên xác nhận đơn khách chưa cọc online (khách sẽ cọc tại cửa hàng khi nhận máy)."""
    don = khoa_don(pk)
    if don.trang_thai != DonThue.CHO_XU_LY:
        raise ValidationError('Yêu cầu đã được xử lý trước đó.')
    phan_bo_may(don)
    gui_thong_bao(don.khach_hang, f'{don.ma} đã được xác nhận. Bạn có thể cọc lịch online {tien(don.tien_coc_giu_lich)}; '
                  'phần cọc máy còn lại thu khi nhận máy.', don)
    return don


@transaction.atomic
def huy_yeu_cau(pk, ly_do, khach_hang=None, dieu_chinh=False):
    don = khoa_don(pk)
    if khach_hang and don.khach_hang_id != khach_hang.pk:
        raise ValidationError('Không có quyền xử lý đơn thuê này.')
    if not don.co_the_huy:
        raise ValidationError('Đơn đã được xử lý, không thể thực hiện thao tác này.')
    if dieu_chinh and not ly_do.strip():
        raise ValidationError('Vui lòng nhập lý do hoặc gợi ý cho khách.')
    if not dieu_chinh and don.ma_giam_gia:
        MaGiamGia.objects.filter(ma=don.ma_giam_gia).update(so_luot=F('so_luot') + 1)
    don.trang_thai = DonThue.CAN_DIEU_CHINH if dieu_chinh else DonThue.DA_HUY
    don.ly_do = ly_do
    don.save(update_fields=['trang_thai', 'ly_do'])
    gui_thong_bao(don.khach_hang, f'{don.ma}: {don.get_trang_thai_display()}. {ly_do}', don)


def ghi_kiem_tra(don, user, loai, du_lieu):
    may_ids = set(PhanBoMay.objects.filter(chi_tiet__don=don).values_list('may_id', flat=True))
    if not may_ids or {d['may'].pk for d in du_lieu} != may_ids or len(du_lieu) != len(may_ids):
        raise ValidationError('Cần kiểm tra đầy đủ từng máy thuộc đơn thuê.')
    for d in du_lieu:
        if not d.get('ben_ngoai', '').strip() or not d.get('hoat_dong', '').strip():
            raise ValidationError('Cần ghi đủ tình trạng bên ngoài và hoạt động của từng máy.')
        if loai == 'giao' and d.get('co_hu_hong'):
            raise ValidationError('Không thể giao máy có hư hỏng. Cần xử lý thiết bị trước.')
        KiemTraThietBi.objects.create(don=don, nhan_vien=user, loai=loai,
            **{key: d.get(key, False if key == 'co_hu_hong' else '')
               for key in ('may', 'ben_ngoai', 'hoat_dong', 'thau_kinh', 'phu_kien', 'co_hu_hong')})


def ghi_giao_dich(don, loai, so_tien, phuong_thuc, user):
    return GiaoDich.objects.create(don=don, loai=loai, so_tien=so_tien, phuong_thuc=phuong_thuc,
                                  nguoi_xac_nhan=user, trang_thai='thanh_cong')


@transaction.atomic
def dat_coc_online(pk, khach_hang):
    """Bước 6 (TO-BE): khách cọc online để giữ máy và lịch, hệ thống báo cọc thành công.

    Website dùng cổng thanh toán mô phỏng: khi khách xác nhận thanh toán, hệ thống ghi giao dịch
    thành công ngay. Muốn dùng cổng thật (VNPay, MoMo) chỉ cần gọi hàm này khi cổng báo về thành công.
    """
    don = khoa_don(pk)
    if don.khach_hang_id != khach_hang.pk:
        raise ValidationError('Không có quyền đặt cọc cho đơn thuê này.')
    if not don.cho_dat_coc:
        raise ValidationError('Đơn không ở trạng thái chờ đặt cọc.')
    if don.gio_tra <= timezone.now():
        raise ValidationError('Đơn đã qua thời gian thuê, không thể đặt cọc.')
    if don.trang_thai == DonThue.CHO_XU_LY:
        # Đơn mới đặt: kiểm tra lại máy trống và giữ máy ngay khi cọc. Lỗi thì không ghi giao dịch nào.
        phan_bo_may(don)
    so_tien = min(don.tien_coc_giu_lich, don.tien_coc_con_lai)
    gd = GiaoDich.objects.create(don=don, loai='dat_coc', so_tien=so_tien, phuong_thuc='online',
        trang_thai='thanh_cong', ma_tham_chieu=f'COC{don.ma}-{uuid.uuid4().hex[:6].upper()}',
        ghi_chu='Cọc lịch giữ máy, được tính vào tiền cọc máy.')
    don.trang_thai_coc, don.hinh_thuc_coc = DonThue.DA_THU, 'online'
    don.save(update_fields=['trang_thai_coc', 'hinh_thuc_coc'])
    gui_thong_bao(don.khach_hang, f'{don.ma}: cọc lịch thành công {tien(so_tien)}. '
                  f'Đã giữ máy; cọc máy còn lại {tien(don.tien_coc_con_lai)} thu khi nhận máy.', don, tieu_de='Đặt cọc thành công')
    for nv in get_user_model().objects.filter(vai_tro__in=['nhan_vien', 'chu_cua_hang'], is_active=True):
        gui_thong_bao(nv, f'{don.ma}: khách đã cọc lịch {tien(so_tien)}, hệ thống đã giữ máy. '
                      f'Cần thu thêm cọc máy {tien(don.tien_coc_con_lai)} khi nhận máy.', don, tieu_de='Khách đã đặt cọc')
    return gd


def tom_tat_kiem_tra(kiem_tra):
    return '; '.join(f"{d['may'].so_seri}: {d.get('ben_ngoai', '').strip()}" for d in kiem_tra)


@transaction.atomic
def giao_may(pk, user, data, kiem_tra=None):
    """Khách nhận máy: thu tiền thuê và phần cọc máy còn thiếu sau cọc lịch.

    kiem_tra (biên bản kiểm tra từng máy) không bắt buộc: trang Tiền cọc chỉ cần một lần xác nhận.
    """
    don = khoa_don(pk)
    if don.trang_thai != DonThue.DA_XAC_NHAN:
        raise ValidationError('Đơn đã giao hoặc không ở trạng thái cho phép giao máy.')
    if not data.get('da_doi_chieu') or not data.get('da_thu_tien_thue'):
        raise ValidationError('Cần đối chiếu CCCD, thông tin đơn, số sê-ri và xác nhận đã thu tiền thuê trước khi giao máy.')
    coc_con_lai = don.tien_coc_con_lai
    if coc_con_lai and not data.get('da_thu_coc'):
        raise ValidationError(f'Cần thu đủ phần cọc máy còn lại {tien(coc_con_lai)} trước khi giao máy.')
    if data['giao_thuc_te'] > timezone.now() or data['giao_thuc_te'] >= don.gio_tra:
        raise ValidationError('Giờ giao phải không ở tương lai và phải trước hạn trả máy.')
    allocations = list(PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may'))
    for p in allocations:
        if p.may.tinh_trang != May.SAN_SANG:
            raise ValidationError(f'{p.may.so_seri} chưa sẵn sàng để giao.')
        if PhanBoMay.objects.filter(may=p.may, chi_tiet__don__trang_thai=DonThue.DANG_THUE).exclude(chi_tiet__don=don).exists():
            raise ValidationError(f'{p.may.so_seri} đang được khách khác thuê.')
    if kiem_tra:
        ghi_kiem_tra(don, user, 'giao', kiem_tra)
    phuong_thuc = data.get('phuong_thuc') or 'tien_mat'
    if coc_con_lai:
        ghi_giao_dich(don, 'dat_coc', coc_con_lai, phuong_thuc, user)
    if don.trang_thai_coc == DonThue.CHUA_THU:
        don.trang_thai_coc, don.hinh_thuc_coc = DonThue.DA_THU, phuong_thuc
    ghi_giao_dich(don, 'thanh_toan', don.tong_thanh_toan, phuong_thuc, user)
    don.giao_thuc_te, don.tinh_trang_khi_giao = data['giao_thuc_te'], tom_tat_kiem_tra(kiem_tra or [])
    don.trang_thai = DonThue.DANG_THUE
    don.save()
    May.objects.filter(pk__in=[p.may_id for p in allocations]).update(tinh_trang=May.DANG_THUE)
    gui_thong_bao(don.khach_hang, f'{don.ma}: đã bàn giao thiết bị. Nhớ trả máy trước {timezone.localtime(don.gio_tra):%H:%M %d/%m}.', don)


@transaction.atomic
def nhan_tra(pk, user, data, kiem_tra=None, anh_su_co=()):
    """Quản lý tiền cọc: khách trả máy thì hoàn cọc.

    Phụ thu trả trễ do hệ thống tự tính theo quy định; đền bù chỉ khấu trừ khi có máy hư hỏng.
    Trang Tiền cọc gửi danh sách máy hư hỏng (data['may_hu_hong']) và ảnh tình trạng máy (anh_su_co)
    thay cho biên bản kiểm tra từng máy.
    """
    don = khoa_don(pk)
    co_bien_ban = kiem_tra is not None
    if not co_bien_ban:
        hu_hong_ids = {m.pk for m in data.get('may_hu_hong') or []}
        kiem_tra = [{'may': p.may, 'ben_ngoai': 'Hư hỏng' if p.may_id in hu_hong_ids else 'Bình thường',
                     'hoat_dong': '', 'co_hu_hong': p.may_id in hu_hong_ids}
                    for p in PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may')]
    if don.trang_thai != DonThue.DANG_THUE or don.trang_thai_coc != DonThue.DA_THU:
        raise ValidationError('Đơn không cho phép nhận trả hoặc tiền cọc chưa được xác nhận.')
    if data['tra_thuc_te'] > timezone.now() or (don.giao_thuc_te and data['tra_thuc_te'] < don.giao_thuc_te):
        raise ValidationError('Giờ nhận trả phải sau giờ giao và không ở tương lai.')
    hu_hong = [d for d in kiem_tra if d.get('co_hu_hong')]
    khau_tru = data.get('khau_tru_den_bu') or 0
    if khau_tru and not hu_hong:
        raise ValidationError('Cần đánh dấu máy hư hỏng trước khi khấu trừ đền bù.')
    if hu_hong and not data.get('mo_ta_su_co', '').strip():
        raise ValidationError('Vui lòng mô tả sự cố của máy.')
    if not data.get('da_xu_ly_tien'):
        raise ValidationError('Cần xác nhận đã nhận đủ máy và đã hoàn cọc / thu thêm đúng số tiền hệ thống tính.')
    if co_bien_ban:
        ghi_kiem_tra(don, user, 'tra', kiem_tra)
    don.phu_thu_tra_tre = tinh_phi_tra_tre(don.gio_tra, data['tra_thuc_te'])
    don.khau_tru_den_bu = khau_tru
    don.hoan_lai = max(don.tien_coc - don.phu_thu_tra_tre - khau_tru, 0)
    don.trang_thai_coc = DonThue.DA_HOAN if don.hoan_lai == don.tien_coc else DonThue.HOAN_MOT_PHAN
    if don.hoan_lai == 0 and don.tien_coc > 0:
        don.trang_thai_coc = DonThue.KHAU_TRU_TOAN_BO
    don.tra_thuc_te, don.hinh_thuc_tra = data['tra_thuc_te'], data['hinh_thuc_tra']
    don.tinh_trang_khi_tra, don.trang_thai = tom_tat_kiem_tra(kiem_tra), DonThue.HOAN_TAT
    don.save()
    for d in kiem_tra:
        may = d['may']
        may.tinh_trang = May.BAO_TRI if d.get('co_hu_hong') else May.SAN_SANG
        if d.get('co_hu_hong') and data.get('loai_su_co') == 'mat_may':
            may.tinh_trang = May.MAT_MAY
        may.save(update_fields=['tinh_trang'])
        if d.get('co_hu_hong'):
            su_co = SuCo.objects.create(don=don, may=may, mo_ta=data['mo_ta_su_co'],
                chi_phi=khau_tru if d is hu_hong[0] else 0, nhan_vien=user,
                loai=data.get('loai_su_co') or 'hu_hong')
            for anh in anh_su_co:
                AnhSuCo.objects.create(su_co=su_co, anh=anh)
    method = data.get('phuong_thuc_hoan') or 'tien_mat'
    if don.hoan_lai:
        ghi_giao_dich(don, 'hoan_coc', don.hoan_lai, method, user)
    if don.can_thu_them:
        ghi_giao_dich(don, 'phu_thu', don.can_thu_them, method, user)
    loi_nhan = f'{don.ma} đã hoàn tất. Hoàn cọc {tien(don.hoan_lai)}'
    if don.phu_thu_tra_tre:
        loi_nhan += f', phụ thu trả trễ {tien(don.phu_thu_tra_tre)}'
    gui_thong_bao(don.khach_hang, loi_nhan + '. Mời bạn gửi đánh giá cho đơn thuê.', don)


@transaction.atomic
def bao_su_co(pk, user, may, loai, mo_ta, anh_su_co):
    """Ghi nhận máy gặp sự cố trong lúc thuê, lưu kèm ảnh tình trạng máy và báo cho khách."""
    don = khoa_don(pk)
    if don.trang_thai not in (DonThue.DA_XAC_NHAN, DonThue.DANG_THUE, DonThue.HOAN_TAT):
        raise ValidationError('Chỉ ghi nhận sự cố cho đơn đã xác nhận, đang thuê hoặc vừa hoàn tất.')
    if not PhanBoMay.objects.filter(chi_tiet__don=don, may=may).exists():
        raise ValidationError('Máy này không thuộc đơn thuê.')
    su_co = SuCo.objects.create(don=don, may=may, loai=loai, mo_ta=mo_ta.strip(), nhan_vien=user)
    for anh in anh_su_co:
        AnhSuCo.objects.create(su_co=su_co, anh=anh)
    gui_thong_bao(don.khach_hang, f'{don.ma}: cửa hàng đã ghi nhận sự cố của máy {may.so_seri}.', don, tieu_de='Sự cố thiết bị')
    return su_co


@transaction.atomic
def phan_bo_lai(pk):
    don = khoa_don(pk)
    if don.trang_thai != DonThue.DA_XAC_NHAN:
        raise ValidationError('Chỉ đổi máy cho đơn đã xác nhận và chưa giao.')
    moi = []
    for dong in don.cac_chi_tiet.select_related('thiet_bi'):
        may = list(cac_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don).select_for_update()[:dong.so_luong])
        if len(may) != dong.so_luong:
            raise ValidationError(f'{dong.thiet_bi.ten}: chưa đủ máy thay thế. Phân bổ cũ được giữ nguyên.')
        moi.extend(PhanBoMay(chi_tiet=dong, may=m) for m in may)
    if not moi:
        raise ValidationError('Đơn chưa có chi tiết thiết bị.')
    PhanBoMay.objects.filter(chi_tiet__don=don).delete()
    PhanBoMay.objects.bulk_create(moi)
    don.may = moi[0].may
    don.save(update_fields=['may'])
    gui_thong_bao(don.khach_hang, f'{don.ma}: cửa hàng đã cập nhật số sê-ri máy được phân bổ. Thiết bị và giá thuê giữ nguyên.', don)

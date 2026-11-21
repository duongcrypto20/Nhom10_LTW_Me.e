"""
Các hàm hỗ trợ dùng chung cho app rentals:

    1. Kiểm tra máy trống theo từng số sê-ri (UC-1.3)
    2. Tính phụ thu trả trễ theo quy định cửa hàng
    3. Gửi thông báo
    4. Dựng lịch tháng của một dòng máy

Quy ước khoảng thời gian thuê: tính từ giờ nhận, không tính giờ trả.
Ví dụ đơn A trả lúc 9h thì đơn B nhận lúc 9h cùng ngày vẫn không bị trùng.
"""
import calendar
import math
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from catalog.models import May

from .models import DonThue, PhanBoMay, ThongBao

# Đơn ở hai trạng thái này đang giữ máy, máy không cho đơn khác thuê
TRANG_THAI_GIU_MAY = [DonThue.DA_XAC_NHAN, DonThue.DANG_THUE]

# Máy ở các tình trạng này không thể cho thuê
TINH_TRANG_KHONG_DUNG_DUOC = [May.BAO_TRI, May.HU_HONG, May.MAT_MAY]

# Quy định "Giờ nhận - trả máy": trễ từ phút thứ 15 thì phụ thu 50.000đ mỗi giờ (làm tròn lên)
PHI_TRE_MOI_GIO = 50_000
SO_PHUT_CHO_PHEP_TRE = 15


# ===========================================================================
# 1. KIỂM TRA MÁY TRỐNG
# ===========================================================================

def dieu_kien_trung_lich(bat_dau, ket_thuc, tien_to=''):
    """
    Điều kiện lọc các đơn bị trùng với khoảng [bat_dau, ket_thuc).

    Hai khoảng trùng nhau khi: giờ nhận của đơn < ket_thuc và giờ trả của đơn > bat_dau.
    Ngoài ra, đơn đang thuê đã quá hạn mà khách chưa trả vẫn giữ máy.
    tien_to dùng khi lọc từ bảng khác, ví dụ 'chi_tiet__don__'.
    """
    trung_khoang = Q(**{
        tien_to + 'gio_nhan__lt': ket_thuc,
        tien_to + 'gio_tra__gt': bat_dau,
    })
    qua_han_chua_tra = Q(**{
        tien_to + 'trang_thai': DonThue.DANG_THUE,
        tien_to + 'gio_tra__lt': timezone.now(),
    })
    return trung_khoang | qua_han_chua_tra


def ds_don_trung_lich(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    """Các đơn đang giữ máy của dòng máy này và bị trùng thời gian."""
    ds = DonThue.objects.filter(
        cac_chi_tiet__thiet_bi=thiet_bi,
        trang_thai__in=TRANG_THAI_GIU_MAY,
    ).filter(dieu_kien_trung_lich(bat_dau, ket_thuc))

    if bo_qua_don:
        ds = ds.exclude(pk=bo_qua_don.pk)
    return ds.distinct()


def cac_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    """
    Danh sách máy (số sê-ri) của dòng máy còn trống trong khoảng thời gian.

    Máy trống = máy dùng được - máy đã được giữ cho đơn khác trùng lịch.
    bo_qua_don: bỏ qua chính đơn đang xử lý (khi đổi máy hoặc kiểm tra lại).
    """
    phan_bo_trung = PhanBoMay.objects.filter(
        chi_tiet__don__trang_thai__in=TRANG_THAI_GIU_MAY,
    ).filter(dieu_kien_trung_lich(bat_dau, ket_thuc, 'chi_tiet__don__'))

    if bo_qua_don:
        phan_bo_trung = phan_bo_trung.exclude(chi_tiet__don=bo_qua_don)

    return (
        thiet_bi.cac_may
        .exclude(tinh_trang__in=TINH_TRANG_KHONG_DUNG_DUOC)
        .exclude(pk__in=phan_bo_trung.values('may_id'))
    )


def dem_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    """Trả về (số máy còn trống, tổng số máy dùng được) của dòng máy."""
    so_trong = cac_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don).count()
    tong = thiet_bi.cac_may.exclude(tinh_trang__in=TINH_TRANG_KHONG_DUNG_DUOC).count()
    return so_trong, tong


# ===========================================================================
# 2. PHỤ THU TRẢ TRỄ
# ===========================================================================

def tinh_phi_tra_tre(gio_tra, tra_thuc_te):
    """
    Phụ thu trả trễ theo quy định cửa hàng.

    Trễ dưới 15 phút: không tính.
    Từ phút thứ 15: 50.000đ cho mỗi giờ, làm tròn lên (trễ 61 phút tính 2 giờ).
    """
    so_phut_tre = (tra_thuc_te - gio_tra).total_seconds() / 60
    if so_phut_tre < SO_PHUT_CHO_PHEP_TRE:
        return 0
    so_gio_tre = math.ceil(so_phut_tre / 60)
    return PHI_TRE_MOI_GIO * so_gio_tre


# ===========================================================================
# 3. THÔNG BÁO
# ===========================================================================

def gui_thong_bao(nguoi_nhan, noi_dung, don=None, tieu_de='Cập nhật đơn thuê'):
    """Tạo một thông báo cho người dùng (nội dung tối đa 255 ký tự)."""
    return ThongBao.objects.create(
        nguoi_nhan=nguoi_nhan,
        tieu_de=tieu_de,
        noi_dung=noi_dung[:255],
        don=don,
    )


# ===========================================================================
# 4. LỊCH THÁNG CỦA MỘT DÒNG MÁY
# ===========================================================================

def don_giu_may_trong_khoang(ds_may, bat_dau, ket_thuc):
    """Trả về dict {id máy: [các đơn đang giữ máy đó trong khoảng thời gian]}."""
    ket_qua = {may.pk: [] for may in ds_may}

    cac_phan_bo = (
        PhanBoMay.objects
        .filter(may__in=ds_may, chi_tiet__don__trang_thai__in=TRANG_THAI_GIU_MAY)
        .filter(dieu_kien_trung_lich(bat_dau, ket_thuc, 'chi_tiet__don__'))
        .select_related('chi_tiet__don__khach_hang')
    )
    for phan_bo in cac_phan_bo:
        don = phan_bo.chi_tiet.don
        if don not in ket_qua[phan_bo.may_id]:
            ket_qua[phan_bo.may_id].append(don)
    return ket_qua


def ket_thuc_giu_may(don):
    """Đơn đang thuê đã quá hạn thì máy vẫn bị giữ cho tới khi khách trả."""
    if don.trang_thai == DonThue.DANG_THUE and don.gio_tra < timezone.now():
        return timezone.now() + timedelta(days=3650)
    return don.gio_tra


def tao_o_ngay(ngay, ds_may, giu_may, hom_nay, ngay_chon):
    """Tạo dữ liệu cho một ô ngày trên lịch: máy nào trống, máy nào đang thuê, bảo trì."""
    bat_dau = timezone.make_aware(datetime.combine(ngay, time.min))
    ket_thuc = bat_dau + timedelta(days=1)

    o_ngay = {
        'ngay': ngay,
        'qua_khu': ngay < hom_nay,
        'hom_nay': ngay == hom_nay,
        'chon': ngay in ngay_chon,
        'trong': [],
        'dang_thue': [],
        'bao_tri': [],
    }

    for may in ds_may:
        # Các đơn giữ máy này trong ngày đang xét
        ds_don = [
            don for don in giu_may[may.pk]
            if don.gio_nhan < ket_thuc and ket_thuc_giu_may(don) > bat_dau
        ]
        if ds_don:
            o_ngay['dang_thue'].append({'may': may, 'don': ds_don[0]})
        elif may.tinh_trang in TINH_TRANG_KHONG_DUNG_DUOC and ngay >= hom_nay:
            o_ngay['bao_tri'].append({'may': may})
        else:
            o_ngay['trong'].append({'may': may})

    # Trạng thái chung của ngày: còn ít nhất 1 máy trống thì hiện "Trống"
    if o_ngay['trong']:
        o_ngay['trang_thai'], o_ngay['nhan'] = 'trong', 'Trống'
    elif o_ngay['dang_thue']:
        o_ngay['trang_thai'], o_ngay['nhan'] = 'thue', 'Đang thuê'
    else:
        o_ngay['trang_thai'], o_ngay['nhan'] = 'bao-tri', 'Bảo trì'
    return o_ngay


def lich_thang(thiet_bi, nam, thang, ngay_chon=None):
    """
    Tạo lịch tháng của một dòng máy để hiển thị dạng bảng 7 cột.

    ngay_chon: tập các ngày khách đang muốn thuê, được tô đậm trên lịch.
    """
    ds_may = list(thiet_bi.cac_may.exclude(tinh_trang=May.MAT_MAY).order_by('so_seri'))
    so_ngay = calendar.monthrange(nam, thang)[1]
    dau_thang = timezone.make_aware(datetime(nam, thang, 1))
    cuoi_thang = dau_thang + timedelta(days=so_ngay)
    giu_may = don_giu_may_trong_khoang(ds_may, dau_thang, cuoi_thang)
    hom_nay = timezone.localdate()

    # Bước 1: tạo dữ liệu cho từng ngày trong tháng
    cac_ngay = []
    for so in range(1, so_ngay + 1):
        o_ngay = tao_o_ngay(date(nam, thang, so), ds_may, giu_may, hom_nay, ngay_chon or set())
        cac_ngay.append(o_ngay)

    # Bước 2: chia thành các tuần, tuần bắt đầu từ thứ Hai (ô trống ở đầu và cuối là None)
    o_trong_dau = [None] * date(nam, thang, 1).weekday()
    tat_ca = o_trong_dau + cac_ngay
    tat_ca += [None] * (-len(tat_ca) % 7)
    cac_tuan = [tat_ca[i:i + 7] for i in range(0, len(tat_ca), 7)]

    # Bước 3: tháng trước và tháng sau để làm nút chuyển tháng
    thang_truoc = (dau_thang - timedelta(days=1)).date()
    thang_sau = cuoi_thang.date()

    return {
        'thiet_bi': thiet_bi,
        'nam': nam,
        'thang': thang,
        'cac_tuan': cac_tuan,
        'so_may': len(ds_may),
        'co_bao_tri': any(o['trang_thai'] == 'bao-tri' and not o['qua_khu'] for o in cac_ngay),
        'thang_truoc': f'{thang_truoc.year}-{thang_truoc.month:02d}',
        'thang_sau': f'{thang_sau.year}-{thang_sau.month:02d}',
    }


def doc_thang(chuoi, mac_dinh=None):
    """Đọc tham số ?thang=YYYY-MM. Sai định dạng thì dùng tháng mặc định."""
    mac_dinh = mac_dinh or timezone.localdate()
    try:
        nam, thang = (int(x) for x in (chuoi or '').split('-'))
        if 2000 <= nam <= 2100 and 1 <= thang <= 12:
            return nam, thang
    except ValueError:
        pass
    return mac_dinh.year, mac_dinh.month


def cac_ngay_trong_khoang(bat_dau, ket_thuc):
    """Tập các ngày (giờ Việt Nam) mà khoảng thuê chạm tới, tối đa 40 ngày."""
    ngay = timezone.localtime(bat_dau).date()
    ngay_cuoi = timezone.localtime(ket_thuc - timedelta(seconds=1)).date()
    ket_qua = set()
    while ngay <= ngay_cuoi and len(ket_qua) < 40:
        ket_qua.add(ngay)
        ngay += timedelta(days=1)
    return ket_qua

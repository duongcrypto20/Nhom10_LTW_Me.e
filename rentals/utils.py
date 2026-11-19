"""Kiểm tra lịch thuê theo từng số sê-ri; khoảng thời gian nhận bao gồm đầu, không gồm cuối."""
import calendar
import math
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from catalog.models import May
from .models import DonThue, PhanBoMay, ThongBao

TRANG_THAI_GIU_MAY = [DonThue.DA_XAC_NHAN, DonThue.DANG_THUE]
TINH_TRANG_KHONG_DUNG_DUOC = [May.BAO_TRI, May.HU_HONG, May.MAT_MAY]

# Quy định "Giờ nhận - trả máy": trả trễ từ phút thứ 15 phụ thu 50.000đ cho mỗi giờ (tính tròn lên)
PHI_TRE_MOI_GIO = 50000
SO_PHUT_CHO_PHEP_TRE = 15


def dieu_kien_trung(bat_dau, ket_thuc, prefix=''):
    return (Q(**{prefix + 'gio_nhan__lt': ket_thuc, prefix + 'gio_tra__gt': bat_dau})
            | Q(**{prefix + 'trang_thai': DonThue.DANG_THUE, prefix + 'gio_tra__lt': timezone.now()}))


def ds_don_trung_lich(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    ds = DonThue.objects.filter(Q(cac_chi_tiet__thiet_bi=thiet_bi) | Q(thiet_bi=thiet_bi),
        trang_thai__in=TRANG_THAI_GIU_MAY).filter(dieu_kien_trung(bat_dau, ket_thuc))
    return (ds.exclude(pk=bo_qua_don.pk) if bo_qua_don else ds).distinct()


def cac_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    pb = PhanBoMay.objects.filter(chi_tiet__don__trang_thai__in=TRANG_THAI_GIU_MAY).filter(
        dieu_kien_trung(bat_dau, ket_thuc, 'chi_tiet__don__'))
    cu = DonThue.objects.filter(trang_thai__in=TRANG_THAI_GIU_MAY).filter(dieu_kien_trung(bat_dau, ket_thuc))
    if bo_qua_don:
        pb, cu = pb.exclude(chi_tiet__don=bo_qua_don), cu.exclude(pk=bo_qua_don.pk)
    return thiet_bi.cac_may.exclude(tinh_trang__in=TINH_TRANG_KHONG_DUNG_DUOC).exclude(
        pk__in=pb.values('may_id')).exclude(pk__in=cu.values('may_id'))


def dem_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don=None):
    return (cac_may_trong(thiet_bi, bat_dau, ket_thuc, bo_qua_don).count(),
            thiet_bi.cac_may.exclude(tinh_trang__in=TINH_TRANG_KHONG_DUNG_DUOC).count())


def chon_may_trong(don):
    return cac_may_trong(don.thiet_bi, don.gio_nhan, don.gio_tra, don).first()


def tinh_phi_tra_tre(gio_tra, tra_thuc_te):
    """Phụ thu trả trễ theo quy định: dưới 15 phút không tính, sau đó 50.000đ mỗi giờ."""
    so_phut_tre = (tra_thuc_te - gio_tra).total_seconds() / 60
    if so_phut_tre < SO_PHUT_CHO_PHEP_TRE:
        return 0
    return PHI_TRE_MOI_GIO * math.ceil(so_phut_tre / 60)


def gui_thong_bao(nguoi_nhan, noi_dung, don=None, tieu_de='Cập nhật đơn thuê'):
    return ThongBao.objects.create(nguoi_nhan=nguoi_nhan, noi_dung=noi_dung[:255], don=don, tieu_de=tieu_de)


# ---------------------------------------------------------------------------
# Lịch tháng: trạng thái từng máy theo ngày (Trống / Đang thuê / Bảo trì)
# ---------------------------------------------------------------------------

def don_giu_may_trong_khoang(ds_may, bat_dau, ket_thuc):
    """Trả về dict {id máy: [đơn đang giữ máy trong khoảng thời gian]}."""
    ket_qua = {may.pk: [] for may in ds_may}
    pb = PhanBoMay.objects.filter(may__in=ds_may, chi_tiet__don__trang_thai__in=TRANG_THAI_GIU_MAY).filter(
        dieu_kien_trung(bat_dau, ket_thuc, 'chi_tiet__don__')).select_related('chi_tiet__don__khach_hang')
    for p in pb:
        if p.chi_tiet.don not in ket_qua[p.may_id]:
            ket_qua[p.may_id].append(p.chi_tiet.don)
    # Đơn cũ chỉ lưu một máy ở trường DonThue.may
    for don in DonThue.objects.filter(may__in=ds_may, trang_thai__in=TRANG_THAI_GIU_MAY, cac_chi_tiet__isnull=True).filter(
            dieu_kien_trung(bat_dau, ket_thuc)).select_related('khach_hang'):
        ket_qua[don.may_id].append(don)
    return ket_qua


def ket_thuc_giu_may(don):
    """Máy đang thuê mà quá hạn vẫn bị giữ tới khi khách trả."""
    if don.trang_thai == DonThue.DANG_THUE and don.gio_tra < timezone.now():
        return timezone.now() + timedelta(days=3650)
    return don.gio_tra


def lich_thang(thiet_bi, nam, thang, ngay_chon=None):
    """Tạo lịch tháng của một dòng máy.

    Mỗi ô ngày cho biết số máy Trống, Đang thuê (đã được giữ cho đơn) và Bảo trì.
    ngay_chon là tập ngày khách đang muốn thuê để tô đậm trên lịch.
    """
    ds_may = list(thiet_bi.cac_may.exclude(tinh_trang=May.MAT_MAY).order_by('so_seri'))
    so_ngay = calendar.monthrange(nam, thang)[1]
    dau_thang = timezone.make_aware(datetime(nam, thang, 1))
    cuoi_thang = dau_thang + timedelta(days=so_ngay)
    giu_may = don_giu_may_trong_khoang(ds_may, dau_thang, cuoi_thang)
    hom_nay = timezone.localdate()
    ngay_chon = ngay_chon or set()

    cac_ngay = []
    for so in range(1, so_ngay + 1):
        ngay = date(nam, thang, so)
        bat_dau = timezone.make_aware(datetime.combine(ngay, time.min))
        ket_thuc = bat_dau + timedelta(days=1)
        o = {'ngay': ngay, 'qua_khu': ngay < hom_nay, 'hom_nay': ngay == hom_nay,
             'chon': ngay in ngay_chon, 'trong': [], 'dang_thue': [], 'bao_tri': []}
        for may in ds_may:
            ds_don = [d for d in giu_may[may.pk] if d.gio_nhan < ket_thuc and ket_thuc_giu_may(d) > bat_dau]
            if ds_don:
                o['dang_thue'].append({'may': may, 'don': ds_don[0]})
            elif may.tinh_trang in TINH_TRANG_KHONG_DUNG_DUOC and ngay >= hom_nay:
                o['bao_tri'].append({'may': may})
            else:
                o['trong'].append({'may': may})
        # Trạng thái chung của ngày để khách xem: còn ít nhất 1 máy là Trống
        if o['trong']:
            o['trang_thai'], o['nhan'] = 'trong', 'Trống'
        elif o['dang_thue']:
            o['trang_thai'], o['nhan'] = 'thue', 'Đang thuê'
        else:
            o['trang_thai'], o['nhan'] = 'bao-tri', 'Bảo trì'
        cac_ngay.append(o)

    # Chia thành các tuần, tuần bắt đầu từ thứ Hai
    o_dau = [None] * date(nam, thang, 1).weekday()
    tat_ca = o_dau + cac_ngay
    tat_ca += [None] * (-len(tat_ca) % 7)
    cac_tuan = [tat_ca[i:i + 7] for i in range(0, len(tat_ca), 7)]

    thang_truoc = (dau_thang - timedelta(days=1)).date()
    thang_sau = cuoi_thang.date()
    return {'thiet_bi': thiet_bi, 'nam': nam, 'thang': thang, 'cac_tuan': cac_tuan, 'so_may': len(ds_may),
            'co_bao_tri': any(o['trang_thai'] == 'bao-tri' and not o['qua_khu'] for o in cac_ngay),
            'thang_truoc': f'{thang_truoc.year}-{thang_truoc.month:02d}',
            'thang_sau': f'{thang_sau.year}-{thang_sau.month:02d}'}


def doc_thang(chuoi, mac_dinh=None):
    """Đọc tham số ?thang=YYYY-MM, sai định dạng thì dùng tháng mặc định."""
    mac_dinh = mac_dinh or timezone.localdate()
    try:
        nam, thang = (int(x) for x in (chuoi or '').split('-'))
        if 2000 <= nam <= 2100 and 1 <= thang <= 12:
            return nam, thang
    except ValueError:
        pass
    return mac_dinh.year, mac_dinh.month


def cac_ngay_trong_khoang(bat_dau, ket_thuc):
    """Tập ngày (giờ địa phương) mà khoảng thuê chạm tới."""
    ngay, cuoi = timezone.localtime(bat_dau).date(), timezone.localtime(ket_thuc - timedelta(seconds=1)).date()
    ket_qua = set()
    while ngay <= cuoi and len(ket_qua) < 40:
        ket_qua.add(ngay)
        ngay += timedelta(days=1)
    return ket_qua

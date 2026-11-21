"""
Các màn hình của app rentals.

    Phần A. Khách hàng : đặt thuê, xác nhận đơn, đặt cọc, xem / sửa / hủy đơn, thông báo
    Phần B. Nhân viên  : tổng quan, yêu cầu thuê, chi tiết đơn, đổi máy, hủy đơn
    Phần C. Tiền cọc   : danh sách tiền cọc, thu cọc khi nhận máy, hoàn cọc khi trả máy
    Phần D. Lịch máy và báo cáo doanh thu
    Phần E. Sự cố máy  : danh sách, ghi nhận (mức độ, mô tả, ảnh hỏng), cập nhật xử lý
"""
import math
import uuid
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import chu_cua_hang_required, khach_hang_required, nhan_vien_required
from catalog.forms import KiemTraMayTrongForm
from catalog.models import GoiThue, May, ThietBi

from . import services
from .forms import DatThueForm, GhiNhanSuCoForm, HoanCocForm, ThuCocForm, XuLySuCoForm, XuLyYeuCauForm
from .models import DonThue, GiaoDich, SuCo
from .utils import dem_may_trong, doc_thang, ds_don_trung_lich, lich_thang, tinh_phi_tra_tre

# Tên khóa lưu bản nháp đặt thuê trong session
KHOA_SESSION = 'don_tam'


# ===========================================================================
# HÀM HỖ TRỢ
# ===========================================================================

def ds_don():
    """Truy vấn đơn thuê kèm sẵn các bảng liên quan để template không phải truy vấn lại."""
    return (
        DonThue.objects
        .select_related('khach_hang', 'thiet_bi', 'goi_thue')
        .prefetch_related(
            'cac_chi_tiet__thiet_bi',
            'cac_chi_tiet__cac_phan_bo__may',
            'cac_giao_dich',
        )
    )


def loc_don(query, tu_khoa):
    """Tìm đơn theo mã đơn (DH1001), tên khách hoặc số điện thoại."""
    if not tu_khoa:
        return query

    dieu_kien = (
        Q(khach_hang__ho_ten__icontains=tu_khoa)
        | Q(khach_hang__so_dien_thoai__icontains=tu_khoa)
    )
    so = tu_khoa.upper().removeprefix('DH')
    if so.isascii() and so.isdigit():
        dieu_kien |= Q(pk=int(so) - 1000)
    return query.filter(dieu_kien)


def bao_loi(request, loi):
    """Hiện lỗi nghiệp vụ (ValidationError) dưới dạng thông báo đỏ."""
    messages.error(request, ' '.join(loi.messages))


def tao_ban_nhap(form, cac_muc):
    """
    Bản nháp đặt thuê lưu trong session.

    Chỉ lưu lựa chọn của khách, không lưu giá. Giá luôn được tính lại khi xác nhận.
    """
    du_lieu = form.cleaned_data
    return {
        'goi_thue_id': du_lieu['goi_thue'].pk,
        'gio_nhan': du_lieu['gio_nhan'].isoformat(),
        'gio_tra': du_lieu['gio_tra'].isoformat(),
        'cac_muc': cac_muc,
        'ghi_chu': du_lieu.get('ghi_chu', ''),
        'ma_giam_gia': du_lieu.get('ma_giam_gia', ''),
        'ma_gui': str(uuid.uuid4()),
    }


def goi_y_tu_trang_kiem_tra(request, thiet_bi):
    """
    Khách bấm "Đặt thuê" từ trang Kiểm tra máy trống: điền sẵn giờ nhận, giờ trả,
    số lượng và chọn sẵn gói rẻ nhất đủ thời lượng.
    """
    du_lieu = request.GET.copy()
    du_lieu.setdefault('so_luong', '1')
    form = KiemTraMayTrongForm(du_lieu)
    if not form.is_valid():
        return {}

    goi_y = {key: form.cleaned_data[key] for key in ('gio_nhan', 'gio_tra', 'so_luong')}
    so_gio = (goi_y['gio_tra'] - goi_y['gio_nhan']).total_seconds() / 3600

    gia_re_nhat = (
        thiet_bi.cac_gia
        .filter(goi_thue__dang_cung_cap=True, goi_thue__so_gio_toi_da__gte=so_gio)
        .order_by('gia')
        .first()
    )
    if gia_re_nhat:
        goi_y['goi_thue'] = gia_re_nhat.goi_thue_id
    else:
        goi_tuy_chinh = GoiThue.objects.filter(
            dang_cung_cap=True, tuy_chinh=True, so_gio_toi_da__gte=so_gio,
        ).first()
        if goi_tuy_chinh:
            goi_y['goi_thue'] = goi_tuy_chinh.pk
    return goi_y


# ===========================================================================
# PHẦN A. KHÁCH HÀNG
# ===========================================================================

@khach_hang_required
def dat_thue(request, ma):
    """UC-1.1: khách chọn gói thuê và thời gian cho một dòng máy."""
    thiet_bi = get_object_or_404(ThietBi, ma=ma, ngung_cung_cap=False)

    # Điền sẵn dữ liệu: từ bản nháp cũ (khách quay lại sửa) hoặc từ trang kiểm tra máy trống
    gia_tri_dau = {}
    tam = request.session.get(KHOA_SESSION)
    if tam and len(tam.get('cac_muc', [])) == 1 and tam['cac_muc'][0]['thiet_bi_id'] == thiet_bi.pk:
        gia_tri_dau.update(tam)
        gia_tri_dau['goi_thue'] = tam['goi_thue_id']
        gia_tri_dau['so_luong'] = tam['cac_muc'][0]['so_luong']
    if 'gio_nhan' in request.GET or 'gio_tra' in request.GET:
        gia_tri_dau.update(goi_y_tu_trang_kiem_tra(request, thiet_bi))

    form = DatThueForm(request.POST or None, thiet_bi=thiet_bi, initial=gia_tri_dau)

    if request.method == 'POST' and form.is_valid():
        so_luong = form.cleaned_data['so_luong'] or 1
        tam = tao_ban_nhap(form, [{'thiet_bi_id': thiet_bi.pk, 'so_luong': so_luong}])
        try:
            services.kiem_tra_ban_nhap(tam)
            request.session[KHOA_SESSION] = tam
            return redirect('xac_nhan_dat_thue')
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    return render(request, 'rentals/dat_thue.html', {'form': form, 'thiet_bi': thiet_bi})


@khach_hang_required
def xac_nhan_dat_thue(request):
    """UC-1.2: xem lại đơn trước khi gửi. Gửi xong chuyển thẳng sang trang đặt cọc."""
    tam = request.session.get(KHOA_SESSION)
    if not tam:
        messages.info(request, 'Vui lòng chọn thiết bị và thời gian thuê trước.')
        return redirect('ds_may_anh')

    try:
        bao_gia_don = services.kiem_tra_ban_nhap(tam)
        if request.method == 'POST':
            don = services.luu_yeu_cau(request.user, tam)
            request.session.pop(KHOA_SESSION, None)
            messages.success(request, f'Đã tạo đơn {don.ma}. Đặt cọc để cửa hàng giữ máy cho bạn.')
            return redirect('dat_coc', pk=don.pk)
    except ValidationError as loi:
        bao_loi(request, loi)
        return redirect('ds_may_anh')

    # Đơn tạm (chưa lưu) chỉ để hiển thị lên màn hình xác nhận
    don_tam = DonThue(
        khach_hang=request.user,
        thiet_bi=bao_gia_don['cac_dong'][0]['thiet_bi'],
        goi_thue=bao_gia_don['goi_thue'],
        gio_nhan=bao_gia_don['gio_nhan'],
        gio_tra=bao_gia_don['gio_tra'],
        tien_thue=bao_gia_don['tien_thue'],
        tien_coc=bao_gia_don['tien_coc'],
        giam_gia=bao_gia_don['giam_gia'],
        ghi_chu=tam.get('ghi_chu', ''),
        ma_giam_gia=tam.get('ma_giam_gia', ''),
    )
    return render(request, 'rentals/xac_nhan_dat_thue.html', {
        'don': don_tam,
        'cac_dong': bao_gia_don['cac_dong'],
    })


def link_ma_qr_coc(don):
    """Ảnh mã QR chuyển khoản tiền cọc (ảnh có sẵn hoặc tạo bằng VietQR)."""
    ngan_hang = settings.THANH_TOAN
    if ngan_hang.get('anh_qr'):
        return static(ngan_hang['anh_qr'])
    if not (ngan_hang['ngan_hang'] and ngan_hang['so_tai_khoan']):
        return None

    tham_so = urlencode({
        'amount': don.tien_coc_giu_lich,
        'addInfo': f'COC {don.ma}',
        'accountName': ngan_hang['chu_tai_khoan'],
    })
    return (
        f"https://img.vietqr.io/image/{ngan_hang['ngan_hang']}-"
        f"{ngan_hang['so_tai_khoan']}-compact2.png?{tham_so}"
    )


@khach_hang_required
def dat_coc(request, pk):
    """TO-BE bước 6: khách cọc lịch online. Cọc thành công thì hệ thống giữ máy."""
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user)

    if request.method == 'POST':
        if request.POST.get('dong_y') != 'on':
            messages.error(request, 'Vui lòng đồng ý quy định cọc trước khi thanh toán.')
        else:
            try:
                services.dat_coc_online(pk, request.user)
                messages.success(request, 'Đặt cọc thành công. Cửa hàng đã giữ máy cho bạn.')
            except ValidationError as loi:
                bao_loi(request, loi)
        return redirect('dat_coc', pk=pk)

    # Đơn đã hủy, đã sửa... thì không còn ở bước đặt cọc
    if not don.cho_dat_coc and don.trang_thai_coc == DonThue.CHUA_THU:
        messages.info(request, 'Đơn này không ở trạng thái đặt cọc.')
        return redirect('chi_tiet_don', pk=pk)

    coc_online = don.cac_giao_dich.filter(loai=GiaoDich.DAT_COC, phuong_thuc='online').first()
    return render(request, 'rentals/dat_coc.html', {
        'don': don,
        'qr_url': link_ma_qr_coc(don),
        'ngan_hang': settings.THANH_TOAN,
        'giao_dich': coc_online,
    })


@khach_hang_required
def trang_cua_toi(request):
    """Trang tổng quan của khách: số đơn theo trạng thái, đơn và thông báo gần đây."""
    don_cua_khach = ds_don().filter(khach_hang=request.user)
    return render(request, 'rentals/trang_cua_toi.html', {
        'so_cho_xu_ly': don_cua_khach.filter(trang_thai=DonThue.CHO_XU_LY).count(),
        'so_da_xac_nhan': don_cua_khach.filter(trang_thai=DonThue.DA_XAC_NHAN).count(),
        'so_dang_thue': don_cua_khach.filter(trang_thai=DonThue.DANG_THUE).count(),
        'so_hoan_tat': don_cua_khach.filter(trang_thai=DonThue.HOAN_TAT).count(),
        'ds_don_gan_day': don_cua_khach[:5],
        'ds_thong_bao': request.user.cac_thong_bao.all()[:5],
    })


@khach_hang_required
def don_cua_toi(request):
    """UC-1.5: danh sách đơn của khách, lọc theo trạng thái và tìm theo mã đơn."""
    trang_thai = request.GET.get('trang_thai', '')
    tu_khoa = request.GET.get('q', '').strip()

    query = ds_don().filter(khach_hang=request.user)
    if trang_thai:
        query = query.filter(trang_thai=trang_thai)
    query = loc_don(query, tu_khoa)

    return render(request, 'rentals/don_cua_toi.html', {
        'ds_don': Paginator(query, 20).get_page(request.GET.get('page')),
        'ds_trang_thai': DonThue.TRANG_THAI,
        'trang_thai_chon': trang_thai,
        'tu_khoa': tu_khoa,
    })


@khach_hang_required
def chi_tiet_don(request, pk):
    """UC-1.5: theo dõi trạng thái một đơn của khách."""
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user)
    return render(request, 'rentals/chi_tiet_don.html', {
        'don': don,
        'da_danh_gia': hasattr(don, 'danh_gia'),
    })


@khach_hang_required
def sua_don(request, pk):
    """Khách sửa lại gói hoặc thời gian khi nhân viên yêu cầu điều chỉnh."""
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user, trang_thai=DonThue.CAN_DIEU_CHINH)
    gia_tri_cu = {
        ten: getattr(don, ten)
        for ten in ('goi_thue', 'gio_nhan', 'gio_tra', 'ma_giam_gia', 'ghi_chu')
    }
    form = DatThueForm(request.POST or None, ma_da_dung=don.ma_giam_gia, initial=gia_tri_cu)
    form.fields.pop('so_luong')
    cac_dong = list(don.cac_chi_tiet.select_related('thiet_bi'))

    if request.method == 'POST' and form.is_valid():
        try:
            # Đọc dòng máy và số lượng mới của từng dòng (số lượng 0 là bỏ dòng đó)
            cac_muc = []
            for dong in cac_dong:
                thiet_bi_id = int(request.POST.get(f'thiet_bi_{dong.pk}', dong.thiet_bi_id))
                so_luong = int(request.POST.get(f'sl_{dong.pk}', dong.so_luong))
                if so_luong:
                    cac_muc.append({'thiet_bi_id': thiet_bi_id, 'so_luong': so_luong})

            services.luu_yeu_cau(request.user, tao_ban_nhap(form, cac_muc), don.pk)
            messages.success(request, 'Đã gửi lại yêu cầu thuê.')
            return redirect('chi_tiet_don', pk=pk)
        except (ValueError, TypeError):
            form.add_error(None, 'Thiết bị và số lượng không hợp lệ.')
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    return render(request, 'rentals/sua_don.html', {
        'don': don,
        'form': form,
        'cac_dong': cac_dong,
        'ds_thiet_bi': ThietBi.objects.filter(ngung_cung_cap=False),
    })


@khach_hang_required
@require_POST
def huy_don(request, pk):
    """Khách tự hủy đơn (chỉ khi chưa cọc)."""
    get_object_or_404(DonThue, pk=pk, khach_hang=request.user)
    try:
        services.huy_yeu_cau(pk, 'Khách hàng hủy yêu cầu.', khach_hang=request.user)
        messages.success(request, 'Đã hủy yêu cầu thuê.')
    except ValidationError as loi:
        bao_loi(request, loi)
    return redirect('chi_tiet_don', pk=pk)


@login_required
def thong_bao(request):
    """Danh sách thông báo của người đang đăng nhập. POST = đánh dấu tất cả đã đọc."""
    query = request.user.cac_thong_bao.select_related('don')
    if request.method == 'POST':
        query.filter(da_doc=False).update(da_doc=True)
        return redirect('thong_bao')
    return render(request, 'rentals/thong_bao.html', {
        'ds_thong_bao': Paginator(query, 30).get_page(request.GET.get('page')),
    })


# ===========================================================================
# PHẦN B. NHÂN VIÊN XỬ LÝ ĐƠN
# ===========================================================================

@nhan_vien_required
def ql_tong_quan(request):
    """Trang tổng quan của nhân viên: số liệu nhanh và các đơn sắp nhận / sắp trả."""
    sap_toi = list(ds_don().filter(trang_thai__in=[DonThue.DA_XAC_NHAN, DonThue.DANG_THUE]))

    # Đơn đã xác nhận thì mốc là giờ nhận; đơn đang thuê thì mốc là giờ trả
    for don in sap_toi:
        if don.trang_thai == DonThue.DA_XAC_NHAN:
            don.thoi_diem_sap_toi = don.gio_nhan
        else:
            don.thoi_diem_sap_toi = don.gio_tra
    sap_toi.sort(key=lambda don: don.thoi_diem_sap_toi)

    return render(request, 'quanly/tong_quan.html', {
        'so_cho_xu_ly': DonThue.objects.filter(trang_thai=DonThue.CHO_XU_LY).count(),
        'so_dang_thue': DonThue.objects.filter(trang_thai=DonThue.DANG_THUE).count(),
        'so_sap_toi': len(sap_toi),
        'so_may_san_sang': May.objects.filter(tinh_trang=May.SAN_SANG).count(),
        'so_may': May.objects.count(),
        'ds_sap_toi': sap_toi[:10],
        'ds_moi_nhat': ds_don()[:5],
    })


def kiem_tra_du_may(don):
    """Với mỗi dòng của đơn: còn bao nhiêu máy trống, có đủ số lượng khách cần không."""
    ket_qua = []
    for dong in don.cac_chi_tiet.all():
        so_trong, tong = dem_may_trong(dong.thiet_bi, don.gio_nhan, don.gio_tra, don)
        ket_qua.append({
            'dong': dong,
            'con': so_trong,
            'tong': tong,
            'du': so_trong >= dong.so_luong,
        })
    return ket_qua


@nhan_vien_required
def ql_yeu_cau(request):
    """UC-1.4: danh sách yêu cầu thuê, tìm theo mã đơn / tên / SĐT, lọc theo trạng thái."""
    trang_thai = request.GET.get('trang_thai', '')
    tu_khoa = request.GET.get('q', '').strip()

    query = loc_don(ds_don(), tu_khoa)
    if trang_thai:
        query = query.filter(trang_thai=trang_thai)
    trang = Paginator(query, 20).get_page(request.GET.get('page'))

    # Đơn chờ xử lý: cho biết còn đủ máy trống không để nhân viên quyết định nhanh
    for don in trang:
        if don.trang_thai == DonThue.CHO_XU_LY:
            kiem_tra = kiem_tra_du_may(don)
            don.con_trong = 1 if kiem_tra and all(muc['du'] for muc in kiem_tra) else 0
            don.tong_may = sum(muc['tong'] for muc in kiem_tra)

    return render(request, 'quanly/yeu_cau.html', {
        'ds_don': trang,
        'ds_trang_thai': DonThue.TRANG_THAI,
        'trang_thai_chon': trang_thai,
        'tu_khoa': tu_khoa,
    })


@nhan_vien_required
def ql_xu_ly_yeu_cau(request, pk):
    """UC-1.4: xác nhận lịch, yêu cầu khách điều chỉnh hoặc hủy đơn."""
    don = get_object_or_404(ds_don(), pk=pk)
    form = XuLyYeuCauForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        hanh_dong = request.POST.get('hanh_dong')
        ly_do = form.cleaned_data['ly_do']
        try:
            if hanh_dong == 'xac_nhan':
                services.xac_nhan_lich(pk)
            elif hanh_dong == 'dieu_chinh':
                services.huy_yeu_cau(pk, ly_do, dieu_chinh=True)
            elif hanh_dong == 'huy':
                services.huy_yeu_cau(pk, ly_do or 'Khách không tiếp tục thuê.')
            else:
                raise ValidationError('Thao tác xử lý không hợp lệ.')
            messages.success(request, 'Đã xử lý yêu cầu và gửi thông báo cho khách hàng.')
            return redirect('ql_yeu_cau')
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    # Tìm các đơn khác đang giữ máy trùng lịch để nhân viên tham khảo
    kiem_tra = kiem_tra_du_may(don)
    ma_don_trung = set()
    for muc in kiem_tra:
        trung = ds_don_trung_lich(muc['dong'].thiet_bi, don.gio_nhan, don.gio_tra, don)
        ma_don_trung.update(trung.values_list('pk', flat=True))

    return render(request, 'quanly/xu_ly_yeu_cau.html', {
        'don': don,
        'form': form,
        'kiem_tra_trong': kiem_tra,
        'con_trong': 1 if kiem_tra and all(muc['du'] for muc in kiem_tra) else 0,
        'tong_may': sum(muc['tong'] for muc in kiem_tra),
        'don_trung': ds_don().filter(pk__in=ma_don_trung),
    })


@nhan_vien_required
def ql_chi_tiet_don(request, pk):
    """Chi tiết một đơn ở khu vực quản lý (thông tin đơn, máy được giữ, giao dịch)."""
    return render(request, 'quanly/chi_tiet_don.html', {'don': get_object_or_404(ds_don(), pk=pk)})


@nhan_vien_required
@require_POST
def ql_huy_don(request, pk):
    """Hủy đơn đã giữ máy nhưng khách không đặt cọc (máy trở lại lịch trống)."""
    get_object_or_404(DonThue, pk=pk)
    ly_do = request.POST.get('ly_do', '').strip() or 'Khách không đặt cọc để giữ lịch.'
    try:
        services.huy_yeu_cau(pk, ly_do)
        messages.success(request, 'Đã hủy đơn và trả máy về lịch trống.')
    except ValidationError as loi:
        bao_loi(request, loi)
    return redirect('ql_chi_tiet_don', pk=pk)


@nhan_vien_required
@require_POST
def ql_phan_bo_lai(request, pk):
    """Đổi sang máy khác cùng dòng cho đơn đã xác nhận."""
    get_object_or_404(DonThue, pk=pk)
    try:
        services.phan_bo_lai(pk)
        messages.success(request, 'Đã kiểm tra lại lịch và đổi máy cho đơn.')
    except ValidationError as loi:
        bao_loi(request, loi)
    return redirect('ql_chi_tiet_don', pk=pk)


# ===========================================================================
# PHẦN C. TIỀN CỌC (gộp từ phần giao nhận, trả máy và tiền cọc)
# ===========================================================================

TAB_TIEN_COC = {
    'chua_thu': 'Chưa thu cọc',
    'dang_giu': 'Đang giữ cọc',
    'da_hoan': 'Đã hoàn / khấu trừ',
}


@nhan_vien_required
def ql_tien_coc(request):
    """Quản lý tiền cọc: đơn chưa thu cọc, đơn cửa hàng đang giữ cọc và đơn đã hoàn cọc."""
    tab = request.GET.get('tab', 'dang_giu')
    if tab not in TAB_TIEN_COC:
        tab = 'dang_giu'
    tu_khoa = request.GET.get('q', '').strip()

    # Ba nhóm đơn tương ứng ba tab
    chua_thu = DonThue.objects.filter(trang_thai=DonThue.DA_XAC_NHAN, trang_thai_coc=DonThue.CHUA_THU)
    dang_giu = DonThue.objects.filter(
        trang_thai__in=[DonThue.DA_XAC_NHAN, DonThue.DANG_THUE],
        trang_thai_coc=DonThue.DA_THU,
    )
    da_hoan = DonThue.objects.filter(trang_thai=DonThue.HOAN_TAT)

    query = {'chua_thu': chua_thu, 'dang_giu': dang_giu, 'da_hoan': da_hoan}[tab]
    query = query.select_related('khach_hang', 'thiet_bi').prefetch_related(
        'cac_chi_tiet__thiet_bi', 'cac_giao_dich',
    )
    query = loc_don(query, tu_khoa)
    if tab == 'da_hoan':
        query = query.order_by('-tra_thuc_te')
    else:
        query = query.order_by('gio_nhan')

    # Số liệu tóm tắt ở đầu trang
    tong_dang_giu = sum(
        GiaoDich.objects
        .filter(don__in=dang_giu, loai=GiaoDich.DAT_COC)
        .values_list('so_tien', flat=True)
    )
    dau_thang = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    da_hoan_thang = sum(
        GiaoDich.objects
        .filter(loai=GiaoDich.HOAN_COC, ngay_tao__gte=dau_thang)
        .values_list('so_tien', flat=True)
    )

    return render(request, 'quanly/tien_coc.html', {
        'tab': tab,
        'cac_tab': TAB_TIEN_COC,
        'tu_khoa': tu_khoa,
        'bay_gio': timezone.now(),
        'ds_don': Paginator(query, 20).get_page(request.GET.get('page')),
        'so_chua_thu': chua_thu.count(),
        'so_dang_giu': dang_giu.count(),
        'tong_dang_giu': tong_dang_giu,
        'da_hoan_thang': da_hoan_thang,
    })


@nhan_vien_required
def ql_thu_coc(request, pk):
    """Khách đến nhận máy: thu tiền thuê và phần cọc máy còn lại."""
    don = get_object_or_404(ds_don(), pk=pk)
    if don.trang_thai != DonThue.DA_XAC_NHAN:
        messages.error(request, 'Đơn không ở trạng thái chờ nhận máy.')
        return redirect('ql_tien_coc')

    form = ThuCocForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.thu_coc_khi_nhan_may(pk, request.user, form.cleaned_data['phuong_thuc'])
            messages.success(request, f'{don.ma}: đã ghi nhận tiền cọc, khách đã nhận máy.')
            return redirect(reverse('ql_tien_coc') + '?tab=dang_giu')
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    return render(request, 'quanly/thu_coc.html', {'don': don, 'form': form})


@nhan_vien_required
def ql_hoan_coc(request, pk):
    """Khách trả máy: tự tính phụ thu trả trễ, khấu trừ đền bù nếu máy hỏng, hoàn cọc."""
    don = get_object_or_404(ds_don(), pk=pk)
    if don.trang_thai != DonThue.DANG_THUE or don.trang_thai_coc != DonThue.DA_THU:
        messages.error(request, 'Chỉ hoàn cọc cho đơn đang thuê và đã thu cọc.')
        return redirect('ql_tien_coc')

    bay_gio = timezone.localtime().replace(second=0, microsecond=0)
    form = HoanCocForm(
        request.POST or None,
        don=don,
        initial={
            'tra_thuc_te': bay_gio,
            'hinh_thuc_tra': 'truc_tiep',
            # Máy đã ghi nhận sự cố nặng thì được chọn sẵn là "hư hỏng"
            'may_hu_hong': services.ma_may_co_su_co_nang(don),
        },
    )

    if request.method == 'POST' and form.is_valid():
        du_lieu = form.cleaned_data
        try:
            services.hoan_coc_khi_tra_may(
                pk,
                request.user,
                tra_thuc_te=du_lieu['tra_thuc_te'],
                hinh_thuc_tra=du_lieu['hinh_thuc_tra'],
                phuong_thuc=du_lieu['phuong_thuc'],
                may_hu_hong=du_lieu['may_hu_hong'],
                mo_ta_hu_hong=du_lieu['mo_ta_hu_hong'],
                khau_tru_den_bu=du_lieu['khau_tru_den_bu'],
            )
            messages.success(request, f'{don.ma}: đã hoàn cọc và hoàn tất đơn thuê.')
            return redirect(reverse('ql_tien_coc') + '?tab=da_hoan')
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    # Số tiền dự kiến nếu khách trả ngay bây giờ và máy bình thường
    phi_tre = tinh_phi_tra_tre(don.gio_tra, bay_gio)
    so_gio_tre = max(math.ceil((timezone.now() - don.gio_tra).total_seconds() / 3600), 0)

    return render(request, 'quanly/hoan_coc.html', {
        'don': don,
        'form': form,
        'phi_tre': phi_tre,
        'so_gio_tre': so_gio_tre,
        'hoan_du_kien': max(don.tien_coc - phi_tre, 0),
    })


# ===========================================================================
# PHẦN D. LỊCH MÁY VÀ BÁO CÁO DOANH THU
# ===========================================================================

@nhan_vien_required
def ql_lich(request):
    """UC-1.3: lịch tháng của từng dòng máy (Trống / Đang thuê / Bảo trì mỗi ngày)."""
    ds_thiet_bi = list(ThietBi.objects.filter(ngung_cung_cap=False))

    # Dòng máy đang xem: theo tham số ?may=, mặc định là dòng đầu tiên
    thiet_bi = None
    for tb in ds_thiet_bi:
        if tb.ma == request.GET.get('may'):
            thiet_bi = tb
    if thiet_bi is None and ds_thiet_bi:
        thiet_bi = ds_thiet_bi[0]

    lich, ngay_xem = None, None
    if thiet_bi:
        nam, thang = doc_thang(request.GET.get('thang'))
        lich = lich_thang(thiet_bi, nam, thang)

        # Ngày đang được bấm xem chi tiết (?ngay=YYYY-MM-DD)
        ngay_chon = request.GET.get('ngay', '')
        for tuan in lich['cac_tuan']:
            for o_ngay in tuan:
                if o_ngay and o_ngay['ngay'].isoformat() == ngay_chon:
                    ngay_xem = o_ngay

    return render(request, 'quanly/lich.html', {
        'ds_thiet_bi': ds_thiet_bi,
        'thiet_bi': thiet_bi,
        'lich': lich,
        'ngay_xem': ngay_xem,
    })


def doc_khoang_ngay(request):
    """Đọc ?tu=YYYY-MM-DD&den=YYYY-MM-DD, mặc định từ đầu tháng tới hôm nay."""
    hom_nay = timezone.localdate()
    try:
        tu = date.fromisoformat(request.GET.get('tu') or hom_nay.replace(day=1).isoformat())
        den = date.fromisoformat(request.GET.get('den') or hom_nay.isoformat())
    except ValueError:
        messages.error(request, 'Ngày không hợp lệ. Đang hiển thị tháng hiện tại.')
        return hom_nay.replace(day=1), hom_nay

    if tu > den:
        messages.error(request, 'Ngày bắt đầu phải trước ngày kết thúc.')
        tu, den = den, tu
    return tu, den


@chu_cua_hang_required
def ql_bao_cao(request):
    """Báo cáo doanh thu cho chủ cửa hàng, tính theo các đơn đã giao máy trong khoảng ngày."""
    tu, den = doc_khoang_ngay(request)
    ds = list(
        ds_don()
        .filter(
            trang_thai__in=[DonThue.DANG_THUE, DonThue.HOAN_TAT],
            giao_thuc_te__date__gte=tu,
            giao_thuc_te__date__lte=den,
        )
        .order_by('-giao_thuc_te')
    )

    # Doanh thu mỗi đơn và gom theo dòng máy
    theo_may = {}
    for don in ds:
        don.doanh_thu = don.tong_thanh_toan + don.phu_thu_tra_tre + don.khau_tru_den_bu
        for dong in don.cac_chi_tiet.all():
            ten = dong.thiet_bi.ten
            muc = theo_may.setdefault(ten, {'ten': ten, 'so_luot': 0, 'tien_thue': 0})
            muc['so_luot'] += dong.so_luong
            muc['tien_thue'] += dong.thanh_tien

    return render(request, 'quanly/bao_cao.html', {
        'tu': tu,
        'den': den,
        'ds_don': ds,
        'tong_tien_thue': sum(don.tien_thue for don in ds),
        'tong_giam_gia': sum(don.giam_gia for don in ds),
        'tong_phat_sinh': sum(don.phu_thu_tra_tre + don.khau_tru_den_bu for don in ds),
        'tong_doanh_thu': sum(don.doanh_thu for don in ds),
        'theo_may': sorted(theo_may.values(), key=lambda muc: -muc['tien_thue']),
    })


# ===========================================================================
# PHẦN E. SỰ CỐ MÁY
# ===========================================================================

@nhan_vien_required
def ql_su_co(request):
    """Danh sách sự cố, lọc theo mức độ / trạng thái; nhập mã đơn để ghi nhận sự cố mới."""
    # Nhân viên nhập mã đơn ở ô "Ghi nhận sự cố mới" thì chuyển sang trang ghi nhận
    ma_don = request.GET.get('ma_don', '').strip()
    if ma_don:
        don = loc_don(DonThue.objects.all(), ma_don).first()
        if don:
            return redirect('ql_ghi_nhan_su_co', pk=don.pk)
        messages.error(request, f'Không tìm thấy đơn "{ma_don}".')

    muc_do = request.GET.get('muc_do', '')
    trang_thai = request.GET.get('trang_thai', '')
    ds = SuCo.objects.select_related('don', 'may__thiet_bi', 'nhan_vien').prefetch_related('cac_anh')
    if muc_do:
        ds = ds.filter(muc_do=muc_do)
    if trang_thai:
        ds = ds.filter(trang_thai=trang_thai)

    return render(request, 'quanly/su_co.html', {
        'ds_su_co': Paginator(ds, 20).get_page(request.GET.get('page')),
        'ds_muc_do': SuCo.MUC_DO,
        'ds_trang_thai': SuCo.TRANG_THAI,
        'muc_do_chon': muc_do,
        'trang_thai_chon': trang_thai,
        'so_cho_xu_ly': SuCo.objects.filter(trang_thai=SuCo.CHO_XU_LY).count(),
    })


@nhan_vien_required
def ql_ghi_nhan_su_co(request, pk):
    """Trang ghi nhận sự cố: chọn máy, mức độ nhẹ / nặng, mô tả và tải ảnh máy hỏng."""
    don = get_object_or_404(ds_don(), pk=pk)
    form = GhiNhanSuCoForm(request.POST or None, request.FILES or None, don=don)

    if request.method == 'POST' and form.is_valid():
        du_lieu = form.cleaned_data
        try:
            su_co = services.ghi_nhan_su_co(
                pk, request.user, du_lieu['may'], du_lieu['muc_do'], du_lieu['mo_ta'], du_lieu['anh'],
            )
            messages.success(request, 'Đã ghi nhận sự cố và lưu ảnh máy hỏng.')
            return redirect('ql_chi_tiet_su_co', pk=su_co.pk)
        except ValidationError as loi:
            form.add_error(None, ' '.join(loi.messages))

    return render(request, 'quanly/ghi_nhan_su_co.html', {'don': don, 'form': form})


@nhan_vien_required
def ql_chi_tiet_su_co(request, pk):
    """Xem mô tả, ảnh máy hỏng và cập nhật kết quả xử lý sự cố."""
    su_co = get_object_or_404(
        SuCo.objects.select_related('don__khach_hang', 'may__thiet_bi', 'nhan_vien'), pk=pk,
    )
    form = XuLySuCoForm(request.POST or None, instance=su_co)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật xử lý sự cố.')
        return redirect('ql_chi_tiet_su_co', pk=pk)

    return render(request, 'quanly/chi_tiet_su_co.html', {'su_co': su_co, 'form': form})

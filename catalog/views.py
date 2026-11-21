"""
Các màn hình của app catalog.

    Phần A. Trang công khai : trang chủ, danh sách máy, chi tiết máy, kiểm tra máy trống,
                              gói thuê và bảng giá, quy định
    Phần B. Quản lý thiết bị (UC-2)
    Phần C. Quản lý dịch vụ, gói thuê và giá (UC-3)
    Phần D. Mã giảm giá và danh mục thiết bị
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import chu_cua_hang_required, nhan_vien_required
from feedback.models import DanhGia
from rentals.models import DonThue, PhanBoMay
from rentals.utils import cac_ngay_trong_khoang, dem_may_trong, doc_thang, lich_thang

from .forms import (GoiThueForm, KiemTraLichForm, KiemTraMayTrongForm, LoaiThietBiForm,
                    MaGiamGiaForm, MayForm, ThietBiForm)
from .models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

DINH_DANG_GIO = '%Y-%m-%dT%H:%M'


def gio_dia_phuong(thoi_diem):
    """Đổi thời điểm sang chuỗi giờ Việt Nam dạng 2026-11-21T09:00 để đưa lên URL."""
    return timezone.localtime(thoi_diem).strftime(DINH_DANG_GIO)


def render_form_chung(request, form, tieu_de, nut, url_huy, co_file=False):
    """Hiển thị một form đơn giản bằng template dùng chung form_chung.html."""
    return render(request, 'form_chung.html', {
        'form': form,
        'tieu_de': tieu_de,
        'nut': nut,
        'url_huy': url_huy,
        'co_file': co_file,
        'quan_ly': True,
    })


# ===========================================================================
# PHẦN A. TRANG CÔNG KHAI
# ===========================================================================

def trang_chu(request):
    """Trang chủ: vài máy nổi bật, gói thuê và đánh giá đã duyệt."""
    return render(request, 'catalog/trang_chu.html', {
        'ds_thiet_bi': ThietBi.objects.filter(ngung_cung_cap=False)[:4],
        'ds_goi': GoiThue.objects.filter(dang_cung_cap=True)[:4],
        'ds_danh_gia': DanhGia.objects.filter(trang_thai=DanhGia.DA_DUYET)[:4],
    })


def ds_may_anh(request):
    """UC-2.3: danh sách thiết bị, tìm theo tên / hãng và lọc theo danh mục."""
    tu_khoa = request.GET.get('q', '')
    loai = request.GET.get('loai', '')

    ds_thiet_bi = ThietBi.objects.all()
    if tu_khoa:
        ds_thiet_bi = ds_thiet_bi.filter(Q(ten__icontains=tu_khoa) | Q(hang__icontains=tu_khoa))
    if loai:
        ds_thiet_bi = ds_thiet_bi.filter(loai=loai)

    return render(request, 'catalog/ds_may_anh.html', {
        'ds_thiet_bi': ds_thiet_bi,
        'ds_loai': list(LoaiThietBi.objects.values_list('ma', 'ten')),
        'tu_khoa': tu_khoa,
        'loai_chon': loai,
    })


def chi_tiet_may_anh(request, ma):
    """UC-2.3: chi tiết một thiết bị, bảng giá theo gói và đánh giá của khách."""
    thiet_bi = get_object_or_404(ThietBi, ma=ma)
    ds_danh_gia = DanhGia.objects.filter(
        don__cac_chi_tiet__thiet_bi=thiet_bi,
        trang_thai=DanhGia.DA_DUYET,
    ).distinct()

    return render(request, 'catalog/chi_tiet_may_anh.html', {
        'thiet_bi': thiet_bi,
        'ds_gia': thiet_bi.cac_gia.filter(goi_thue__dang_cung_cap=True),
        'ds_danh_gia': ds_danh_gia,
    })


def kiem_tra_lich(request):
    """UC-1.3: khách chọn dòng máy, giờ nhận, giờ trả và xem lịch tháng của dòng máy đó."""
    du_lieu = request.GET if 'thiet_bi' in request.GET else None
    form = KiemTraLichForm(du_lieu, initial={'thiet_bi': request.GET.get('may')})
    ket_qua = None

    if form.is_bound and form.is_valid():
        thiet_bi = form.cleaned_data['thiet_bi']
        nhan = form.cleaned_data['nhan']
        tra = form.cleaned_data['tra']

        so_trong, tong = dem_may_trong(thiet_bi, nhan, tra)
        nam, thang = doc_thang(request.GET.get('thang'), timezone.localtime(nhan).date())
        tham_so = urlencode({
            'gio_nhan': gio_dia_phuong(nhan),
            'gio_tra': gio_dia_phuong(tra),
            'so_luong': 1,
        })

        ket_qua = {
            'thiet_bi': thiet_bi,
            'nhan': nhan,
            'tra': tra,
            'con': so_trong,
            'tong': tong,
            'lich': lich_thang(thiet_bi, nam, thang, cac_ngay_trong_khoang(nhan, tra)),
            'link_dat_thue': reverse('dat_thue', args=[thiet_bi.ma]) + '?' + tham_so,
        }

    return render(request, 'catalog/kiem_tra_lich.html', {'form': form, 'ket_qua': ket_qua})


def kiem_tra_may_trong(request, ma):
    """API nhỏ trả JSON: còn bao nhiêu máy trống của một dòng máy (dùng ở trang chi tiết máy)."""
    thiet_bi = get_object_or_404(ThietBi, ma=ma)
    form = KiemTraMayTrongForm(request.GET)
    if not form.is_valid():
        return JsonResponse({'hop_le': False, 'loi': form.errors.get_json_data()}, status=400)

    du_lieu = form.cleaned_data
    so_trong = 0
    if not thiet_bi.ngung_cung_cap:
        so_trong, _ = dem_may_trong(thiet_bi, du_lieu['gio_nhan'], du_lieu['gio_tra'])
    du_may = so_trong >= du_lieu['so_luong']

    tham_so = urlencode({
        'gio_nhan': gio_dia_phuong(du_lieu['gio_nhan']),
        'gio_tra': gio_dia_phuong(du_lieu['gio_tra']),
        'so_luong': du_lieu['so_luong'],
    })
    link_dat_thue = reverse('dat_thue', args=[thiet_bi.ma]) + '?' + tham_so

    return JsonResponse({
        'hop_le': True,
        'thiet_bi': thiet_bi.ten,
        'so_may_trong': so_trong,
        'so_luong_can': du_lieu['so_luong'],
        'du_may': du_may,
        'dat_thue_url': link_dat_thue if du_may else None,
    })


def tao_bang_gia(ds_thiet_bi, ds_goi):
    """Tạo bảng giá: mỗi dòng là một thiết bị, mỗi ô là giá của thiết bị theo một gói."""
    cac_dong = []
    for thiet_bi in ds_thiet_bi:
        gia_theo_goi = {gia.goi_thue_id: gia.gia for gia in thiet_bi.cac_gia.all()}
        ds_o = [{'goi': goi, 'gia': gia_theo_goi.get(goi.id)} for goi in ds_goi]
        cac_dong.append({'thiet_bi': thiet_bi, 'ds_o': ds_o})
    return cac_dong


def goi_thue(request):
    """UC-3.2: danh sách gói thuê và bảng giá của các máy."""
    ds_goi = GoiThue.objects.filter(dang_cung_cap=True)
    ds_goi_co_gia = ds_goi.filter(tuy_chinh=False)
    ds_thiet_bi = ThietBi.objects.filter(ngung_cung_cap=False)

    return render(request, 'catalog/goi_thue.html', {
        'ds_goi': ds_goi,
        'ds_goi_gia': ds_goi_co_gia,
        'bang_gia': tao_bang_gia(ds_thiet_bi, ds_goi_co_gia),
    })


def quy_dinh(request):
    """Các quy định của cửa hàng (cọc, giờ nhận trả, đền bù, bảo quản máy)."""
    return render(request, 'catalog/quy_dinh.html')


# ===========================================================================
# PHẦN B. QUẢN LÝ THIẾT BỊ (UC-2)
# ===========================================================================

@nhan_vien_required
def ql_thiet_bi(request):
    """Danh sách thiết bị trong khu vực quản lý, tìm theo tên hoặc mã."""
    tu_khoa = request.GET.get('q', '')
    ds_thiet_bi = ThietBi.objects.all()
    if tu_khoa:
        ds_thiet_bi = ds_thiet_bi.filter(Q(ten__icontains=tu_khoa) | Q(ma__icontains=tu_khoa))

    return render(request, 'quanly/thiet_bi.html', {
        'ds_thiet_bi': ds_thiet_bi,
        'tu_khoa': tu_khoa,
    })


@chu_cua_hang_required
def ql_them_thiet_bi(request):
    """UC-2.1: thêm mới thiết bị (chỉ chủ cửa hàng)."""
    form = ThietBiForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm thiết bị thành công.')
        return redirect('ql_thiet_bi')
    return render_form_chung(request, form, 'Thêm thiết bị', 'Lưu thiết bị', 'ql_thiet_bi', co_file=True)


@nhan_vien_required
def ql_sua_thiet_bi(request, pk):
    """UC-2.2: cập nhật thông tin thiết bị và tình trạng từng máy."""
    thiet_bi = get_object_or_404(ThietBi, pk=pk)
    form = ThietBiForm(request.POST or None, request.FILES or None, instance=thiet_bi)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cập nhật thiết bị thành công.')
        return redirect('ql_sua_thiet_bi', pk=thiet_bi.pk)

    return render(request, 'quanly/sua_thiet_bi.html', {
        'form': form,
        'thiet_bi': thiet_bi,
        'may_form': MayForm(),
        'ds_tinh_trang': May.TINH_TRANG,
    })


@chu_cua_hang_required
@require_POST
def ql_them_may(request, pk):
    """Thêm một máy vật lý (số sê-ri) cho thiết bị."""
    thiet_bi = get_object_or_404(ThietBi, pk=pk)
    form = MayForm(request.POST)
    if form.is_valid():
        may = form.save(commit=False)
        may.thiet_bi = thiet_bi
        may.save()
        messages.success(request, 'Đã thêm máy mới.')
    else:
        messages.error(request, 'Số sê-ri không hợp lệ hoặc đã tồn tại.')
    return redirect('ql_sua_thiet_bi', pk=thiet_bi.pk)


@nhan_vien_required
@require_POST
def ql_doi_tinh_trang_may(request, pk):
    """UC-2.2: đổi tình trạng của một máy (sẵn sàng, bảo trì, hư hỏng, mất máy)."""
    may = get_object_or_404(May, pk=pk)
    tinh_trang = request.POST.get('tinh_trang')
    ds_hop_le = [ma for ma, ten in May.TINH_TRANG]

    # Máy đang có khách thuê thì chỉ tự đổi khi nhân viên hoàn cọc
    dang_thue = PhanBoMay.objects.filter(
        may=may,
        chi_tiet__don__trang_thai=DonThue.DANG_THUE,
    ).exists()

    if dang_thue or tinh_trang == May.DANG_THUE:
        messages.error(request, 'Máy đang thuê sẽ tự về Sẵn sàng khi nhân viên hoàn cọc cho đơn.')
    elif tinh_trang not in ds_hop_le:
        messages.error(request, 'Tình trạng không hợp lệ.')
    else:
        may.tinh_trang = tinh_trang
        may.save()
        messages.success(request, 'Đã cập nhật tình trạng máy.')
    return redirect('ql_sua_thiet_bi', pk=may.thiet_bi_id)


# ===========================================================================
# PHẦN C. QUẢN LÝ DỊCH VỤ, GÓI THUÊ VÀ GIÁ (UC-3)
# ===========================================================================

def doc_bang_gia_nhap(post, ds_thiet_bi, ds_goi):
    """
    Đọc các ô giá trong form bảng giá. Mỗi ô có tên dạng gia_<id thiết bị>_<id gói>.

    Trả về (danh sách cần lưu, có lỗi hay không). Ô để trống nghĩa là xóa giá đó.
    """
    ds_can_luu = []
    co_loi = False
    for thiet_bi in ds_thiet_bi:
        for goi in ds_goi:
            ten_o = f'gia_{thiet_bi.id}_{goi.id}'
            if ten_o not in post:
                continue

            gia_nhap = post[ten_o].strip()
            if gia_nhap == '':
                ds_can_luu.append((thiet_bi, goi, None))
            elif gia_nhap.isascii() and gia_nhap.isdigit() and int(gia_nhap) <= 2_147_483_647:
                ds_can_luu.append((thiet_bi, goi, int(gia_nhap)))
            else:
                co_loi = True
    return ds_can_luu, co_loi


@nhan_vien_required
def ql_dich_vu(request):
    """UC-3.2 và UC-3.4: danh sách gói thuê và bảng quản lý giá thuê."""
    ds_goi = GoiThue.objects.all()
    ds_goi_co_gia = ds_goi.filter(tuy_chinh=False)
    ds_thiet_bi = ThietBi.objects.all()

    if request.method == 'POST':
        ds_can_luu, co_loi = doc_bang_gia_nhap(request.POST, ds_thiet_bi, ds_goi_co_gia)
        if co_loi:
            messages.error(request, 'Giá thuê không hợp lệ. Giá phải là số không âm.')
        else:
            # Lưu tất cả ô giá trong một transaction
            with transaction.atomic():
                for thiet_bi, goi, gia in ds_can_luu:
                    if gia is None:
                        GiaThue.objects.filter(thiet_bi=thiet_bi, goi_thue=goi).delete()
                    else:
                        GiaThue.objects.update_or_create(
                            thiet_bi=thiet_bi, goi_thue=goi, defaults={'gia': gia},
                        )
            messages.success(request, 'Lưu giá thuê thành công.')
            return redirect('ql_dich_vu')

    return render(request, 'quanly/dich_vu.html', {
        'ds_goi': ds_goi,
        'ds_goi_gia': ds_goi_co_gia,
        'bang_gia': tao_bang_gia(ds_thiet_bi, ds_goi_co_gia),
    })


@chu_cua_hang_required
def ql_them_goi(request):
    """UC-3.1: thêm mới gói thuê (chỉ chủ cửa hàng)."""
    form = GoiThueForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm gói thuê thành công.')
        return redirect('ql_dich_vu')
    return render_form_chung(request, form, 'Thêm gói thuê', 'Lưu gói thuê', 'ql_dich_vu')


@nhan_vien_required
def ql_sua_goi(request, pk):
    """UC-3.3: cập nhật gói thuê."""
    goi = get_object_or_404(GoiThue, pk=pk)
    form = GoiThueForm(request.POST or None, instance=goi)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cập nhật gói thuê thành công.')
        return redirect('ql_dich_vu')
    return render_form_chung(request, form, f'Cập nhật gói {goi.ten}', 'Lưu cập nhật', 'ql_dich_vu')


# ===========================================================================
# PHẦN D. MÃ GIẢM GIÁ VÀ DANH MỤC THIẾT BỊ
# ===========================================================================

@nhan_vien_required
def ql_ma_giam_gia(request):
    """Danh sách mã giảm giá."""
    return render(request, 'quanly/ma_giam_gia.html', {'ds_ma': MaGiamGia.objects.all()})


@chu_cua_hang_required
def ql_them_ma_giam_gia(request):
    """Thêm mã giảm giá (chỉ chủ cửa hàng)."""
    form = MaGiamGiaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm mã giảm giá thành công.')
        return redirect('ql_ma_giam_gia')
    return render_form_chung(request, form, 'Thêm mã giảm giá', 'Lưu mã', 'ql_ma_giam_gia')


@chu_cua_hang_required
def ql_sua_ma_giam_gia(request, pk):
    """Sửa giá trị, số lượt, thời hạn của mã giảm giá."""
    ma_giam_gia = get_object_or_404(MaGiamGia, pk=pk)
    form = MaGiamGiaForm(request.POST or None, instance=ma_giam_gia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật mã giảm giá.')
        return redirect('ql_ma_giam_gia')
    return render_form_chung(request, form, f'Cập nhật mã {ma_giam_gia.ma}', 'Lưu mã giảm giá', 'ql_ma_giam_gia')


@chu_cua_hang_required
def ql_danh_muc(request):
    """Danh sách và thêm danh mục thiết bị (Mirrorless, Compact...)."""
    form = LoaiThietBiForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã thêm danh mục thiết bị.')
        return redirect('ql_danh_muc')
    return render(request, 'quanly/danh_muc.html', {
        'form': form,
        'ds_danh_muc': LoaiThietBi.objects.all(),
    })

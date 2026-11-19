from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from urllib.parse import urlencode

from accounts.decorators import chu_cua_hang_required, nhan_vien_required
from feedback.models import DanhGia

from .forms import GoiThueForm, KiemTraLichForm, KiemTraMayTrongForm, LoaiThietBiForm, MaGiamGiaForm, MayForm, ThietBiForm
from .models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

# ---------------------------------------------------------------------------
# Trang công khai
# ---------------------------------------------------------------------------

def trang_chu(request):
    ds_thiet_bi = ThietBi.objects.filter(ngung_cung_cap=False)[:4]
    ds_goi = GoiThue.objects.filter(dang_cung_cap=True)[:4]
    ds_danh_gia = DanhGia.objects.filter(trang_thai=DanhGia.DA_DUYET)[:4]
    return render(request, 'catalog/trang_chu.html', {
        'ds_thiet_bi': ds_thiet_bi,
        'ds_goi': ds_goi,
        'ds_danh_gia': ds_danh_gia,
    })


def ds_may_anh(request):
    """UC-2.3: Xem danh sách thiết bị, có tìm kiếm và lọc theo loại."""
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
    """UC-2.3: Xem thông tin chi tiết một thiết bị."""
    thiet_bi = get_object_or_404(ThietBi, ma=ma)
    ds_gia = thiet_bi.cac_gia.filter(goi_thue__dang_cung_cap=True)
    ds_danh_gia = DanhGia.objects.filter(Q(don__cac_chi_tiet__thiet_bi=thiet_bi) | Q(don__thiet_bi=thiet_bi),
                                        trang_thai=DanhGia.DA_DUYET).distinct()
    return render(request, 'catalog/chi_tiet_may_anh.html', {
        'thiet_bi': thiet_bi,
        'ds_gia': ds_gia,
        'ds_danh_gia': ds_danh_gia,
    })


def kiem_tra_lich(request):
    """Kiểm tra máy trống: khách chọn dòng máy, ngày giờ nhận / trả rồi xem lịch tháng của dòng máy đó."""
    from rentals.utils import cac_ngay_trong_khoang, dem_may_trong, doc_thang, lich_thang
    form = KiemTraLichForm(request.GET if 'thiet_bi' in request.GET else None,
                           initial={'thiet_bi': request.GET.get('may')})
    ket_qua = None
    if form.is_bound and form.is_valid():
        thiet_bi, nhan, tra = form.cleaned_data['thiet_bi'], form.cleaned_data['nhan'], form.cleaned_data['tra']
        con, tong = dem_may_trong(thiet_bi, nhan, tra)
        nam, thang = doc_thang(request.GET.get('thang'), timezone.localtime(nhan).date())
        tham_so = urlencode({'gio_nhan': timezone.localtime(nhan).strftime('%Y-%m-%dT%H:%M'),
                             'gio_tra': timezone.localtime(tra).strftime('%Y-%m-%dT%H:%M'), 'so_luong': 1})
        ket_qua = {
            'thiet_bi': thiet_bi, 'nhan': nhan, 'tra': tra, 'con': con, 'tong': tong,
            'lich': lich_thang(thiet_bi, nam, thang, cac_ngay_trong_khoang(nhan, tra)),
            'link_dat_thue': reverse('dat_thue', args=[thiet_bi.ma]) + '?' + tham_so,
        }
    return render(request, 'catalog/kiem_tra_lich.html', {'form': form, 'ket_qua': ket_qua})


def gan_ket_qua_trong(thiet_bi, data):
    from rentals.utils import dem_may_trong
    con, tong = dem_may_trong(thiet_bi, data['gio_nhan'], data['gio_tra'])
    thiet_bi.so_may_trong_lich = con if not thiet_bi.ngung_cung_cap else 0
    thiet_bi.da_kiem_tra_lich = True
    thiet_bi.du_may = thiet_bi.so_may_trong_lich >= data['so_luong']
    params = urlencode({k: timezone.localtime(data[k]).strftime('%Y-%m-%dT%H:%M') for k in ('gio_nhan', 'gio_tra')}
                       | {'so_luong': data['so_luong']})
    thiet_bi.link_dat_thue = reverse('dat_thue', args=[thiet_bi.ma]) + '?' + params
    thiet_bi.link_chi_tiet = reverse('chi_tiet_may_anh', args=[thiet_bi.ma]) + '?' + params


def kiem_tra_may_trong(request, ma):
    thiet_bi = get_object_or_404(ThietBi, ma=ma)
    form = KiemTraMayTrongForm(request.GET)
    if not form.is_valid():
        return JsonResponse({'hop_le': False, 'loi': form.errors.get_json_data()}, status=400)
    gan_ket_qua_trong(thiet_bi, form.cleaned_data)
    return JsonResponse({'hop_le': True, 'thiet_bi': thiet_bi.ten, 'so_may_trong': thiet_bi.so_may_trong_lich,
        'so_luong_can': form.cleaned_data['so_luong'], 'du_may': thiet_bi.du_may,
        'dat_thue_url': thiet_bi.link_dat_thue if thiet_bi.du_may else None})


def tao_bang_gia(ds_thiet_bi, ds_goi):
    """Tạo danh sách dòng cho bảng giá: mỗi dòng gồm thiết bị và giá theo từng gói."""
    cac_dong = []
    for thiet_bi in ds_thiet_bi:
        gia_theo_goi = {}
        for gia in thiet_bi.cac_gia.all():
            gia_theo_goi[gia.goi_thue_id] = gia.gia
        ds_o = []
        for goi in ds_goi:
            ds_o.append({'goi': goi, 'gia': gia_theo_goi.get(goi.id)})
        cac_dong.append({'thiet_bi': thiet_bi, 'ds_o': ds_o})
    return cac_dong


def goi_thue(request):
    """UC-3.2: Xem danh sách gói thuê và bảng giá."""
    ds_goi = GoiThue.objects.filter(dang_cung_cap=True)
    ds_thiet_bi = ThietBi.objects.filter(ngung_cung_cap=False)
    return render(request, 'catalog/goi_thue.html', {
        'ds_goi': ds_goi,
        'ds_goi_gia': ds_goi.filter(tuy_chinh=False),
        'bang_gia': tao_bang_gia(ds_thiet_bi, ds_goi.filter(tuy_chinh=False)),
    })


def quy_dinh(request):
    return render(request, 'catalog/quy_dinh.html')



# ---------------------------------------------------------------------------
# Khu vực quản lý: thiết bị
# ---------------------------------------------------------------------------

@nhan_vien_required
def ql_thiet_bi(request):
    tu_khoa = request.GET.get('q', '')
    ds_thiet_bi = ThietBi.objects.all()
    if tu_khoa:
        ds_thiet_bi = ds_thiet_bi.filter(Q(ten__icontains=tu_khoa) | Q(ma__icontains=tu_khoa))
    return render(request, 'quanly/thiet_bi.html', {'ds_thiet_bi': ds_thiet_bi, 'tu_khoa': tu_khoa})


@chu_cua_hang_required
def ql_them_thiet_bi(request):
    """UC-2.1: Thêm mới thiết bị (chỉ chủ cửa hàng)."""
    form = ThietBiForm((request.POST if request.method == 'POST' else None), request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm thiết bị thành công.')
        return redirect('ql_thiet_bi')
    return render(request, 'form_chung.html', {
        'form': form, 'tieu_de': 'Thêm thiết bị', 'nut': 'Lưu thiết bị',
        'url_huy': 'ql_thiet_bi', 'co_file': True, 'quan_ly': True,
    })


@nhan_vien_required
def ql_sua_thiet_bi(request, pk):
    """UC-2.2: Cập nhật thông tin và tình trạng thiết bị."""
    thiet_bi = get_object_or_404(ThietBi, pk=pk)
    form = ThietBiForm((request.POST if request.method == 'POST' else None), request.FILES or None, instance=thiet_bi)
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
    """UC-2.2: Cập nhật tình trạng của một máy vật lý."""
    may = get_object_or_404(May, pk=pk)
    tinh_trang = request.POST.get('tinh_trang')
    ds_hop_le = [ma for ma, ten in May.TINH_TRANG]
    from rentals.models import DonThue, PhanBoMay
    dang_thue = (PhanBoMay.objects.filter(may=may, chi_tiet__don__trang_thai=DonThue.DANG_THUE).exists()
                  or may.cac_don.filter(trang_thai=DonThue.DANG_THUE).exists())
    if dang_thue or tinh_trang == May.DANG_THUE:
        messages.error(request, 'Máy đang thuê sẽ tự về Sẵn sàng khi nhân viên hoàn cọc cho đơn.')
    elif tinh_trang in ds_hop_le:
        may.tinh_trang = tinh_trang
        may.save()
        messages.success(request, 'Đã cập nhật tình trạng máy.')
    else:
        messages.error(request, 'Tình trạng không hợp lệ.')
    return redirect('ql_sua_thiet_bi', pk=may.thiet_bi_id)


# ---------------------------------------------------------------------------
# Khu vực quản lý: dịch vụ, gói thuê và giá
# ---------------------------------------------------------------------------

@nhan_vien_required
def ql_dich_vu(request):
    """UC-3.2 và UC-3.4: Danh sách gói thuê và bảng quản lý giá thuê."""
    ds_goi = GoiThue.objects.all()
    ds_thiet_bi = ThietBi.objects.all()

    if request.method == 'POST':
        # Mỗi ô giá có tên dạng gia_<id thiết bị>_<id gói>
        co_loi = False
        ds_can_luu = []
        for thiet_bi in ds_thiet_bi:
            for goi in ds_goi.filter(tuy_chinh=False):
                key = f'gia_{thiet_bi.id}_{goi.id}'
                if key not in request.POST:
                    continue
                gia_nhap = request.POST[key].strip()
                if gia_nhap == '':
                    ds_can_luu.append((thiet_bi, goi, None))
                    continue
                if not gia_nhap.isascii() or not gia_nhap.isdigit() or int(gia_nhap) > 2147483647:
                    co_loi = True
                    continue
                ds_can_luu.append((thiet_bi, goi, int(gia_nhap)))

        if co_loi:
            messages.error(request, 'Giá thuê không hợp lệ. Giá phải là số không âm.')
        else:
            with transaction.atomic():
                for thiet_bi, goi, gia in ds_can_luu:
                    if gia is None:
                        GiaThue.objects.filter(thiet_bi=thiet_bi, goi_thue=goi).delete()
                    else:
                        GiaThue.objects.update_or_create(thiet_bi=thiet_bi, goi_thue=goi, defaults={'gia': gia})
            messages.success(request, 'Lưu giá thuê thành công.')
            return redirect('ql_dich_vu')

    ds_goi_co_dinh = ds_goi.filter(tuy_chinh=False)
    return render(request, 'quanly/dich_vu.html', {
        'ds_goi': ds_goi,
        'ds_goi_gia': ds_goi_co_dinh,
        'bang_gia': tao_bang_gia(ds_thiet_bi, ds_goi_co_dinh),
    })


@chu_cua_hang_required
def ql_them_goi(request):
    """UC-3.1: Thêm mới gói thuê (chỉ chủ cửa hàng)."""
    form = GoiThueForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm gói thuê thành công.')
        return redirect('ql_dich_vu')
    return render(request, 'form_chung.html', {
        'form': form, 'tieu_de': 'Thêm gói thuê', 'nut': 'Lưu gói thuê',
        'url_huy': 'ql_dich_vu', 'quan_ly': True,
    })


@nhan_vien_required
def ql_sua_goi(request, pk):
    """UC-3.3: Cập nhật gói thuê."""
    goi = get_object_or_404(GoiThue, pk=pk)
    form = GoiThueForm((request.POST if request.method == 'POST' else None), instance=goi)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cập nhật gói thuê thành công.')
        return redirect('ql_dich_vu')
    return render(request, 'form_chung.html', {
        'form': form, 'tieu_de': f'Cập nhật gói {goi.ten}', 'nut': 'Lưu cập nhật',
        'url_huy': 'ql_dich_vu', 'quan_ly': True,
    })


# ---------------------------------------------------------------------------
# Khu vực quản lý: mã giảm giá
# ---------------------------------------------------------------------------

@nhan_vien_required
def ql_ma_giam_gia(request):
    return render(request, 'quanly/ma_giam_gia.html', {'ds_ma': MaGiamGia.objects.all()})


@chu_cua_hang_required
def ql_them_ma_giam_gia(request):
    form = MaGiamGiaForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Thêm mã giảm giá thành công.')
        return redirect('ql_ma_giam_gia')
    return render(request, 'form_chung.html', {
        'form': form, 'tieu_de': 'Thêm mã giảm giá', 'nut': 'Lưu mã',
        'url_huy': 'ql_ma_giam_gia', 'quan_ly': True,
    })


@chu_cua_hang_required
def ql_sua_ma_giam_gia(request, pk):
    obj = get_object_or_404(MaGiamGia, pk=pk)
    form = MaGiamGiaForm((request.POST if request.method == 'POST' else None), instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã cập nhật mã giảm giá.')
        return redirect('ql_ma_giam_gia')
    return render(request, 'form_chung.html', {'form': form, 'tieu_de': f'Cập nhật mã {obj.ma}',
        'nut': 'Lưu mã giảm giá', 'url_huy': 'ql_ma_giam_gia'})


@chu_cua_hang_required
def ql_danh_muc(request):
    form = LoaiThietBiForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã thêm danh mục thiết bị.')
        return redirect('ql_danh_muc')
    return render(request, 'quanly/danh_muc.html', {'form': form, 'ds_danh_muc': LoaiThietBi.objects.all()})

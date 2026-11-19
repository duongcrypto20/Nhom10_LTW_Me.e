from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from django.db import transaction
from rentals.services import khoa_don
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import khach_hang_required, nhan_vien_required
from rentals.models import DonThue
from rentals.utils import gui_thong_bao

import os
from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from catalog.models import ThietBi

from .forms import LocPhanHoiForm, TraLoiForm, VietDanhGiaForm
from .models import DanhGia


@khach_hang_required
def phan_hoi_cua_toi(request):
    don_cho = DonThue.objects.filter(khach_hang=request.user, trang_thai=DonThue.HOAN_TAT,
        danh_gia__isnull=True).select_related('thiet_bi', 'goi_thue').prefetch_related('cac_chi_tiet__thiet_bi')
    phan_hoi = DanhGia.objects.filter(don__khach_hang=request.user).select_related('don', 'don__thiet_bi')
    return render(request, 'feedback/cua_toi.html', {'don_cho_phan_hoi': don_cho,
        'ds_phan_hoi': Paginator(phan_hoi, 20).get_page(request.GET.get('page'))})


def thong_ke_sao(ds_danh_gia):
    """UC-4.4: Tính điểm trung bình và số lượng theo từng mức sao."""
    tong = ds_danh_gia.count()
    trung_binh = ds_danh_gia.aggregate(tb=Avg('so_sao'))['tb'] or 0
    theo_sao = []
    for sao in [5, 4, 3, 2, 1]:
        so_luong = ds_danh_gia.filter(so_sao=sao).count()
        phan_tram = so_luong * 100 // tong if tong else 0
        theo_sao.append({'sao': sao, 'so_luong': so_luong, 'phan_tram': phan_tram})
    return {'tong': tong, 'trung_binh': round(trung_binh, 1), 'theo_sao': theo_sao}


def loc_phan_hoi(request, query, cong_khai=False):
    form = LocPhanHoiForm(request.GET)
    if cong_khai:
        form.fields.pop('trang_thai')
        form.fields.pop('tra_loi')
    if not form.is_valid():
        return form, query.none()
    data = form.cleaned_data
    if data.get('thiet_bi'):
        from rentals.models import ChiTietDonThue
        ids = ChiTietDonThue.objects.filter(thiet_bi=data['thiet_bi']).values('don_id')
        query = query.filter(Q(don_id__in=ids) | Q(don__thiet_bi=data['thiet_bi']))
    for key, lookup in (('goi_thue', 'don__goi_thue'), ('so_sao', 'so_sao'),
                         ('tu_ngay', 'ngay_tao__date__gte'), ('den_ngay', 'ngay_tao__date__lte'), ('trang_thai', 'trang_thai')):
        if data.get(key):
            query = query.filter(**{lookup: data[key]})
    if data.get('tra_loi') == 'co':
        query = query.exclude(tra_loi='')
    elif data.get('tra_loi') == 'chua':
        query = query.filter(tra_loi='')
    return form, query


def anh_cua_hang(thiet_bi=None):
    """Ảnh feedback khách gửi cho cửa hàng, lưu trong static/img/feedback/<mã máy>-<số>.jpg."""
    thu_muc = settings.BASE_DIR / 'static' / 'img' / 'feedback'
    if not thu_muc.is_dir():
        return []
    ten_may = dict(ThietBi.objects.values_list('ma', 'ten'))
    ds = []
    for ten_file in sorted(os.listdir(thu_muc)):
        ma = ten_file.rsplit('-', 1)[0]
        if thiet_bi and ma != thiet_bi.ma:
            continue
        ds.append({'url': static(f'img/feedback/{ten_file}'), 'ten_may': ten_may.get(ma, ''), 'nguoi': 'Khách của me.e'})
    return ds


def trang_danh_gia(request, form_viet=None):
    """UC-4.2: Xem phản hồi. Trang gồm: tất cả ảnh feedback, ô viết đánh giá, đánh giá của bạn, đánh giá đã duyệt."""
    ds = DanhGia.objects.filter(trang_thai=DanhGia.DA_DUYET).select_related('don__khach_hang', 'don__thiet_bi')
    form_loc, ds = loc_phan_hoi(request, ds, cong_khai=True)
    thiet_bi = form_loc.cleaned_data.get('thiet_bi') if form_loc.is_valid() else None
    # Ảnh: ảnh khách tải lên khi đánh giá (đã duyệt) đứng trước, sau đó là ảnh feedback của cửa hàng
    ds_anh = [{'url': dg.anh.url, 'ten_may': dg.don.ten_thiet_bi, 'nguoi': dg.don.khach_hang.ho_ten, 'sao': dg.cac_sao}
              for dg in ds if dg.anh]
    ds_anh += anh_cua_hang(thiet_bi)

    la_khach = request.user.is_authenticated and request.user.la_khach_hang
    if la_khach and form_viet is None:
        form_viet = VietDanhGiaForm(user=request.user, initial={'don': request.GET.get('don')})
    return render(request, 'feedback/ds_danh_gia.html', {
        'form_loc': form_loc, 'ds_danh_gia': Paginator(ds, 20).get_page(request.GET.get('page')),
        'thong_ke': thong_ke_sao(ds), 'ds_anh': ds_anh, 'thiet_bi_chon': thiet_bi,
        'ds_thiet_bi': ThietBi.objects.filter(ngung_cung_cap=False),
        'form_viet': form_viet, 'mo_form': bool(form_viet and (form_viet.errors or request.GET.get('don'))),
        'cua_toi': DanhGia.objects.filter(don__khach_hang=request.user).select_related('don') if la_khach else None,
    })


def luu_danh_gia(request, form):
    """UC-4.1 bước 8: lưu phản hồi, mỗi đơn chỉ một lần, báo cho nhân viên."""
    with transaction.atomic():
        don = khoa_don(form.cleaned_data['don'].pk)
        if DanhGia.objects.filter(don=don).exists():
            messages.info(request, 'Phản hồi của bạn cho đơn này đã được ghi nhận trước đó.')
            return redirect(reverse('ds_danh_gia') + '#danh-gia-cua-ban')
        danh_gia = form.save(commit=False)
        danh_gia.don = don
        danh_gia.save()
    from accounts.models import User
    for nv in User.objects.filter(vai_tro__in=[User.NHAN_VIEN, User.CHU_CUA_HANG], is_active=True):
        gui_thong_bao(nv, f'{don.ma}: khách vừa gửi đánh giá {danh_gia.so_sao} sao.', don, tieu_de='Phản hồi mới')
    messages.success(request, 'Gửi đánh giá thành công. Đánh giá hiện công khai sau khi cửa hàng duyệt.')
    return redirect(reverse('ds_danh_gia') + '#danh-gia-cua-ban')


def ds_danh_gia(request):
    if request.method == 'POST':
        if not (request.user.is_authenticated and request.user.la_khach_hang):
            return redirect(reverse('dang_nhap') + '?next=' + reverse('ds_danh_gia'))
        form = VietDanhGiaForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            return luu_danh_gia(request, form)
        return trang_danh_gia(request, form)
    return trang_danh_gia(request)


@khach_hang_required
def gui_danh_gia(request, don_pk):
    """UC-4.1: Gửi phản hồi cho một đơn cụ thể (từ trang đơn thuê). Dùng chung form với trang Đánh giá."""
    don = get_object_or_404(DonThue, pk=don_pk, khach_hang=request.user)
    # BR01: chỉ đơn đã hoàn tất mới được phản hồi; mỗi đơn một lần
    if don.trang_thai != DonThue.HOAN_TAT:
        messages.error(request, 'Chỉ gửi phản hồi được cho đơn đã hoàn tất.')
        return redirect('chi_tiet_don', pk=don.pk)
    if hasattr(don, 'danh_gia'):
        messages.error(request, 'Bạn đã gửi phản hồi cho đơn này.')
        return redirect('chi_tiet_don', pk=don.pk)
    if request.method != 'POST':
        return redirect(reverse('ds_danh_gia') + f'?don={don.pk}#viet-danh-gia')
    data = request.POST.copy()
    data['don'] = don.pk
    form = VietDanhGiaForm(data, request.FILES, user=request.user)
    if form.is_valid():
        return luu_danh_gia(request, form)
    return trang_danh_gia(request, form)


@nhan_vien_required
def ql_phan_hoi(request):
    """UC-4.3 và UC-4.4: danh sách phản hồi, lọc theo điều kiện và thống kê."""
    ds = DanhGia.objects.select_related('don__khach_hang', 'don__thiet_bi', 'don__goi_thue')
    form, ds = loc_phan_hoi(request, ds)
    from rentals.models import ChiTietDonThue
    theo_thiet_bi = (ChiTietDonThue.objects.filter(don__danh_gia__in=ds).order_by().values('thiet_bi__ten')
                     .annotate(so_luong=Count('don__danh_gia', distinct=True), diem=Avg('don__danh_gia__so_sao'))
                     .order_by('-so_luong'))
    return render(request, 'quanly/phan_hoi.html', {
        'form_loc': form, 'ds_danh_gia': Paginator(ds, 20).get_page(request.GET.get('page')),
        'thong_ke': thong_ke_sao(ds),
        'so_cho_xu_ly': ds.filter(trang_thai=DanhGia.CHO_XU_LY).count(),
        'so_da_tra_loi': ds.exclude(tra_loi='').count(),
        'theo_goi': ds.order_by().values('don__goi_thue__ten').annotate(so_luong=Count('pk', distinct=True), diem=Avg('so_sao')),
        'theo_thiet_bi': theo_thiet_bi,
    })


def doi_trang_thai(request, danh_gia, hanh_dong):
    """UC-4.3: duyệt hoặc ẩn. Báo lỗi nếu phản hồi đã ở trạng thái đó (E2)."""
    moi = {'duyet': DanhGia.DA_DUYET, 'an': DanhGia.DA_AN}.get(hanh_dong)
    if moi is None:
        messages.error(request, 'Thao tác xử lý phản hồi không hợp lệ.')
    elif danh_gia.trang_thai == moi:
        messages.info(request, 'Phản hồi đã được xử lý trước đó.')
    else:
        danh_gia.trang_thai = moi
        danh_gia.save(update_fields=['trang_thai'])
        messages.success(request, 'Đã duyệt phản hồi, khách hàng khác có thể xem.' if moi == DanhGia.DA_DUYET
                         else 'Đã ẩn phản hồi khỏi trang công khai.')


@nhan_vien_required
@require_POST
def ql_doi_trang_thai_phan_hoi(request, pk):
    danh_gia = get_object_or_404(DanhGia, pk=pk)
    doi_trang_thai(request, danh_gia, request.POST.get('hanh_dong'))
    if request.POST.get('tiep') == 'chi_tiet':
        return redirect('ql_chi_tiet_phan_hoi', pk=pk)
    return redirect('ql_phan_hoi')


@nhan_vien_required
def ql_chi_tiet_phan_hoi(request, pk):
    """UC-4.3 + UC-4.5: xem chi tiết một phản hồi, duyệt/ẩn và trả lời ngay trên một trang."""
    danh_gia = get_object_or_404(DanhGia.objects.select_related('don__khach_hang', 'don__goi_thue'), pk=pk)
    form = TraLoiForm((request.POST if request.method == 'POST' else None), instance=danh_gia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        gui_thong_bao(danh_gia.don.khach_hang, f'Cửa hàng đã trả lời feedback của bạn cho đơn {danh_gia.don.ma}.',
                      danh_gia.don, tieu_de='Cửa hàng trả lời feedback')
        messages.success(request, 'Đã lưu câu trả lời. Khách hàng sẽ thấy câu trả lời ngay dưới đánh giá của mình.')
        return redirect('ql_chi_tiet_phan_hoi', pk=pk)
    return render(request, 'quanly/chi_tiet_phan_hoi.html', {'dg': danh_gia, 'form': form})

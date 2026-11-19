"""Màn hình đặt thuê, kiểm tra lịch, kiểm tra đơn, quản lý tiền cọc và sự cố máy."""
import math
import uuid
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import chu_cua_hang_required, khach_hang_required, nhan_vien_required
from catalog.models import May, ThietBi
from catalog.pricing import bao_gia
from . import services
from .forms import (BaoSuCoForm, DatThueForm, HoanCocForm, NhanCocForm, SuCoForm,
                    ThemAnhSuCoForm, TraMayForm, XuLyYeuCauForm)
from .models import AnhSuCo, DonThue, GiaoDich, SuCo
from .utils import (dem_may_trong, doc_thang, ds_don_trung_lich, lich_thang,
                    tinh_phi_tra_tre)

KHOA_SESSION = 'don_tam'


def loi_form(form, exc):
    form.add_error(None, ' '.join(exc.messages))


def ds_don():
    return DonThue.objects.select_related('khach_hang', 'thiet_bi', 'goi_thue', 'may').prefetch_related(
        'cac_chi_tiet__thiet_bi', 'cac_chi_tiet__cac_phan_bo__may', 'cac_giao_dich')


def loc_don(query, tu_khoa):
    if not tu_khoa:
        return query
    dk = Q(khach_hang__ho_ten__icontains=tu_khoa) | Q(khach_hang__so_dien_thoai__icontains=tu_khoa)
    so = tu_khoa.upper().removeprefix('DH')
    if so.isascii() and so.isdigit():
        dk |= Q(pk=int(so) - 1000)
    return query.filter(dk)


def ban_nhap(form, cac_muc):
    data = form.cleaned_data
    return {**{k: data.get(k, '') for k in ('ghi_chu', 'ma_giam_gia')},
            'goi_thue_id': data['goi_thue'].pk, 'gio_nhan': data['gio_nhan'].isoformat(),
            'gio_tra': data['gio_tra'].isoformat(), 'cac_muc': cac_muc, 'ma_gui': str(uuid.uuid4())}


@khach_hang_required
def dat_thue(request, ma):
    tb = get_object_or_404(ThietBi, ma=ma, ngung_cung_cap=False)
    initial = {}
    tam = request.session.get(KHOA_SESSION)
    if tam and len(tam.get('cac_muc', [])) == 1 and tam['cac_muc'][0]['thiet_bi_id'] == tb.pk:
        initial.update(tam, goi_thue=tam['goi_thue_id'], so_luong=tam['cac_muc'][0]['so_luong'])
    if 'gio_nhan' in request.GET or 'gio_tra' in request.GET:
        from catalog.forms import KiemTraMayTrongForm
        data = request.GET.copy()
        data.setdefault('so_luong', '1')
        kiem_tra = KiemTraMayTrongForm(data)
        if kiem_tra.is_valid():
            initial.update({key: kiem_tra.cleaned_data[key] for key in ('gio_nhan', 'gio_tra', 'so_luong')})
            so_gio = (initial['gio_tra'] - initial['gio_nhan']).total_seconds() / 3600
            gia = tb.cac_gia.filter(goi_thue__dang_cung_cap=True,
                goi_thue__so_gio_toi_da__gte=so_gio).order_by('gia').first()
            if gia:
                initial['goi_thue'] = gia.goi_thue_id
            else:
                from catalog.models import GoiThue
                custom = GoiThue.objects.filter(dang_cung_cap=True, tuy_chinh=True, so_gio_toi_da__gte=so_gio).first()
                if custom:
                    initial['goi_thue'] = custom.pk
    form = DatThueForm((request.POST if request.method == 'POST' else None), thiet_bi=tb, initial=initial)
    if request.method == 'POST' and form.is_valid():
        tam = ban_nhap(form, [{'thiet_bi_id': tb.pk, 'so_luong': form.cleaned_data['so_luong'] or 1}])
        try:
            services.kiem_tra_ban_nhap(tam)
            request.session[KHOA_SESSION] = tam
            return redirect('xac_nhan_dat_thue')
        except ValidationError as exc:
            loi_form(form, exc)
    return render(request, 'rentals/dat_thue.html', {'form': form, 'thiet_bi': tb})


@khach_hang_required
def xac_nhan_dat_thue(request):
    tam = request.session.get(KHOA_SESSION)
    if not tam:
        messages.info(request, 'Vui lòng chọn thiết bị và thời gian thuê trước.')
        return redirect('ds_may_anh')
    try:
        goi, nhan, tra, dong, tong, coc, voucher, giam = services.kiem_tra_ban_nhap(tam)
        if request.method == 'POST':
            don = services.luu_yeu_cau(request.user, tam)
            request.session.pop(KHOA_SESSION, None)
            messages.success(request, f'Đã tạo đơn {don.ma}. Đặt cọc để cửa hàng giữ máy và lịch cho bạn.')
            return redirect('dat_coc', pk=don.pk)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('ds_may_anh')
    don = DonThue(khach_hang=request.user, thiet_bi=dong[0][0], goi_thue=goi, gio_nhan=nhan,
        gio_tra=tra, tien_thue=tong, tien_coc=coc, giam_gia=giam, **{k: tam.get(k, '') for k in ('ghi_chu', 'ma_giam_gia')})
    return render(request, 'rentals/xac_nhan_dat_thue.html', {'don': don,
        'cac_dong': [{'thiet_bi': tb, 'so_luong': sl, 'thanh_tien': sl * gia,
            'cach_tinh_gia': bao_gia(tb, goi, nhan, tra)[1]} for tb, sl, gia in dong]})


@khach_hang_required
def trang_cua_toi(request):
    query = ds_don().filter(khach_hang=request.user)
    return render(request, 'rentals/trang_cua_toi.html', {
        'so_cho_xu_ly': query.filter(trang_thai=DonThue.CHO_XU_LY).count(),
        'so_da_xac_nhan': query.filter(trang_thai=DonThue.DA_XAC_NHAN).count(),
        'so_dang_thue': query.filter(trang_thai=DonThue.DANG_THUE).count(),
        'so_hoan_tat': query.filter(trang_thai=DonThue.HOAN_TAT).count(),
        'ds_don_gan_day': query[:5], 'ds_thong_bao': request.user.cac_thong_bao.all()[:5]})


@khach_hang_required
def don_cua_toi(request):
    state = request.GET.get('trang_thai', '')
    query = ds_don().filter(khach_hang=request.user)
    if state:
        query = query.filter(trang_thai=state)
    keyword = request.GET.get('q', '').strip()
    query = loc_don(query, keyword)
    return render(request, 'rentals/don_cua_toi.html', {'ds_don': Paginator(query, 20).get_page(request.GET.get('page')),
        'ds_trang_thai': DonThue.TRANG_THAI, 'trang_thai_chon': state, 'tu_khoa': keyword})


@khach_hang_required
def chi_tiet_don(request, pk):
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user)
    return render(request, 'rentals/chi_tiet_don.html', {'don': don, 'da_danh_gia': hasattr(don, 'danh_gia'),
        'form_tra': TraMayForm(initial={'hinh_thuc_tra': don.hinh_thuc_tra or 'truc_tiep',
        'ma_van_don_tra': don.ma_van_don_tra, 'don_vi_van_chuyen': don.don_vi_van_chuyen})})


def ma_qr_coc(don):
    """Ảnh mã VietQR để chuyển khoản tiền cọc (chỉ có khi đã cấu hình tài khoản ngân hàng)."""
    bank = settings.THANH_TOAN
    if bank.get('anh_qr'):
        return static(bank['anh_qr'])
    if not (bank['ngan_hang'] and bank['so_tai_khoan']):
        return None
    return f"https://img.vietqr.io/image/{bank['ngan_hang']}-{bank['so_tai_khoan']}-compact2.png?" + urlencode(
        {'amount': don.tien_coc_giu_lich, 'addInfo': f'COC {don.ma}', 'accountName': bank['chu_tai_khoan']})


@khach_hang_required
def dat_coc(request, pk):
    """Trang thanh toán cọc: khách vào ngay sau khi xác nhận đặt đơn. Cọc thành công thì hệ thống giữ máy."""
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user)
    if request.method == 'POST':
        if request.POST.get('dong_y') != 'on':
            messages.error(request, 'Vui lòng đồng ý quy định cọc trước khi thanh toán.')
        else:
            try:
                services.dat_coc_online(pk, request.user)
                messages.success(request, 'Đặt cọc thành công. Cửa hàng đã giữ máy và lịch cho bạn.')
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
        return redirect('dat_coc', pk=pk)
    if not don.cho_dat_coc and don.trang_thai_coc == DonThue.CHUA_THU:
        messages.info(request, 'Đơn này không ở trạng thái đặt cọc.')
        return redirect('chi_tiet_don', pk=pk)
    return render(request, 'rentals/dat_coc.html', {'don': don, 'qr_url': ma_qr_coc(don),
        'ngan_hang': settings.THANH_TOAN, 'giao_dich': don.cac_giao_dich.filter(loai='dat_coc',
            phuong_thuc='online', trang_thai='thanh_cong').first()})


@khach_hang_required
def sua_don(request, pk):
    don = get_object_or_404(ds_don(), pk=pk, khach_hang=request.user, trang_thai=DonThue.CAN_DIEU_CHINH)
    initial = {name: getattr(don, name) for name in ('goi_thue', 'gio_nhan', 'gio_tra', 'ma_giam_gia', 'ghi_chu')}
    form = DatThueForm((request.POST if request.method == 'POST' else None), voucher_da_dung=don.ma_giam_gia, initial=initial)
    form.fields.pop('so_luong')
    dong = list(don.cac_chi_tiet.select_related('thiet_bi'))
    if request.method == 'POST' and form.is_valid():
        try:
            cac_muc = []
            for d in dong:
                tb = get_object_or_404(ThietBi, pk=request.POST.get(f'thiet_bi_{d.pk}', d.thiet_bi_id))
                sl = int(request.POST.get(f'sl_{d.pk}', d.so_luong))
                if sl:
                    cac_muc.append({'thiet_bi_id': tb.pk, 'so_luong': sl})
            services.luu_yeu_cau(request.user, ban_nhap(form, cac_muc), don.pk)
            messages.success(request, 'Đã gửi lại yêu cầu thuê.')
            return redirect('chi_tiet_don', pk=pk)
        except (ValueError, TypeError):
            form.add_error(None, 'Thiết bị và số lượng không hợp lệ.')
        except ValidationError as exc:
            loi_form(form, exc)
    return render(request, 'rentals/sua_don.html', {'don': don, 'form': form, 'cac_dong': dong,
                                                  'ds_thiet_bi': ThietBi.objects.filter(ngung_cung_cap=False)})


@khach_hang_required
@require_POST
def huy_don(request, pk):
    get_object_or_404(DonThue, pk=pk, khach_hang=request.user)
    try:
        services.huy_yeu_cau(pk, 'Khách hàng hủy yêu cầu.', khach_hang=request.user)
        messages.success(request, 'Đã hủy yêu cầu thuê.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('chi_tiet_don', pk=pk)


@khach_hang_required
def bao_tra_may(request, pk):
    don = get_object_or_404(DonThue, pk=pk, khach_hang=request.user, trang_thai=DonThue.DANG_THUE)
    form = TraMayForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            don = services.khoa_don(pk)
            if don.trang_thai != DonThue.DANG_THUE:
                messages.error(request, 'Đơn đã được xử lý nhận trả.')
                return redirect('chi_tiet_don', pk=pk)
            for name, value in form.cleaned_data.items():
                setattr(don, name, value)
            don.ngay_bao_tra = timezone.now()
            don.save()
        messages.success(request, 'Đã báo hình thức trả máy. Đơn hoàn tất sau khi cửa hàng nhận và kiểm tra thiết bị.')
        return redirect('chi_tiet_don', pk=pk)
    return render(request, 'form_chung.html', {'form': form, 'tieu_de': 'Thông báo trả máy',
        'nut': 'Gửi thông tin trả máy', 'url_huy': 'don_cua_toi'})


@login_required
def thong_bao(request):
    query = request.user.cac_thong_bao.select_related('don')
    if request.method == 'POST':
        query.filter(da_doc=False).update(da_doc=True)
        return redirect('thong_bao')
    return render(request, 'rentals/thong_bao.html', {'ds_thong_bao': Paginator(query, 30).get_page(request.GET.get('page'))})


@nhan_vien_required
def ql_tong_quan(request):
    sap_toi = ds_don().filter(trang_thai__in=[DonThue.DA_XAC_NHAN, DonThue.DANG_THUE]).order_by('gio_nhan')
    return render(request, 'quanly/tong_quan.html', {'so_cho_xu_ly': DonThue.objects.filter(trang_thai=DonThue.CHO_XU_LY).count(),
        'so_dang_thue': DonThue.objects.filter(trang_thai=DonThue.DANG_THUE).count(), 'so_sap_toi': sap_toi.count(),
        'so_may_san_sang': May.objects.filter(tinh_trang=May.SAN_SANG).count(), 'so_may': May.objects.count(),
        'ds_sap_toi': sap_toi[:10], 'ds_moi_nhat': ds_don()[:5]})


@nhan_vien_required
def ql_yeu_cau(request):
    state, keyword = request.GET.get('trang_thai', ''), request.GET.get('q', '').strip()
    query = loc_don(ds_don(), keyword)
    if state:
        query = query.filter(trang_thai=state)
    page = Paginator(query, 20).get_page(request.GET.get('page'))
    for don in page:
        if don.trang_thai == DonThue.CHO_XU_LY:
            checks = [(dem_may_trong(d.thiet_bi, don.gio_nhan, don.gio_tra, don), d.so_luong) for d in don.cac_chi_tiet.all()]
            don.con_trong = 1 if checks and all(c[0][0] >= c[1] for c in checks) else 0
            don.tong_may = sum(c[0][1] for c in checks)
    return render(request, 'quanly/yeu_cau.html', {'ds_don': page, 'ds_trang_thai': DonThue.TRANG_THAI,
        'trang_thai_chon': state, 'tu_khoa': keyword})


@nhan_vien_required
def ql_xu_ly_yeu_cau(request, pk):
    don = get_object_or_404(ds_don(), pk=pk)
    form = XuLyYeuCauForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        try:
            action = request.POST.get('hanh_dong')
            if action == 'xac_nhan':
                services.xac_nhan_lich(pk)
            elif action in ('dieu_chinh', 'huy'):
                services.huy_yeu_cau(pk, form.cleaned_data['ly_do'] or ('Khách không tiếp tục thuê.' if action == 'huy' else ''),
                                      dieu_chinh=action == 'dieu_chinh')
            else:
                raise ValidationError('Thao tác xử lý không hợp lệ.')
            messages.success(request, 'Đã xử lý yêu cầu và gửi thông báo cho khách hàng.')
            return redirect('ql_yeu_cau')
        except ValidationError as exc:
            loi_form(form, exc)
    checks, trung = [], set()
    for d in don.cac_chi_tiet.all():
        con, tong = dem_may_trong(d.thiet_bi, don.gio_nhan, don.gio_tra, don)
        checks.append({'dong': d, 'con': con, 'tong': tong, 'du': con >= d.so_luong})
        trung.update(ds_don_trung_lich(d.thiet_bi, don.gio_nhan, don.gio_tra, don).values_list('pk', flat=True))
    return render(request, 'quanly/xu_ly_yeu_cau.html', {'don': don, 'kiem_tra_trong': checks,
        'con_trong': 1 if checks and all(c['du'] for c in checks) else 0,
        'tong_may': sum(c['tong'] for c in checks), 'don_trung': ds_don().filter(pk__in=trung), 'form': form})


@nhan_vien_required
def ql_kiem_tra_don(request):
    """Kiểm tra thông tin đơn thuê: tìm theo mã đơn, tên hoặc số điện thoại khách, lọc theo trạng thái."""
    tu_khoa = request.GET.get('q', '').strip()
    trang_thai = request.GET.get('trang_thai', '')
    query = loc_don(ds_don(), tu_khoa).order_by('-ngay_tao')
    if trang_thai:
        query = query.filter(trang_thai=trang_thai)
    return render(request, 'quanly/kiem_tra_don.html', {
        'ds_don': Paginator(query, 20).get_page(request.GET.get('page')),
        'tu_khoa': tu_khoa, 'trang_thai_chon': trang_thai, 'ds_trang_thai': DonThue.TRANG_THAI})


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
    giu_may = [DonThue.DA_XAC_NHAN, DonThue.DANG_THUE]
    chua_thu = DonThue.objects.filter(trang_thai=DonThue.DA_XAC_NHAN, trang_thai_coc=DonThue.CHUA_THU)
    dang_giu = DonThue.objects.filter(trang_thai__in=giu_may, trang_thai_coc=DonThue.DA_THU)
    da_hoan = DonThue.objects.filter(trang_thai=DonThue.HOAN_TAT)
    query = {'chua_thu': chua_thu, 'dang_giu': dang_giu, 'da_hoan': da_hoan}[tab]
    query = loc_don(query.select_related('khach_hang', 'thiet_bi').prefetch_related('cac_chi_tiet__thiet_bi', 'cac_giao_dich'), tu_khoa)
    query = query.order_by('-tra_thuc_te') if tab == 'da_hoan' else query.order_by('gio_nhan')
    dau_thang = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return render(request, 'quanly/tien_coc.html', {
        'tab': tab, 'cac_tab': TAB_TIEN_COC, 'tu_khoa': tu_khoa, 'bay_gio': timezone.now(),
        'ds_don': Paginator(query, 20).get_page(request.GET.get('page')),
        'so_chua_thu': chua_thu.count(), 'so_dang_giu': dang_giu.count(),
        'tong_dang_giu': sum(GiaoDich.objects.filter(don__in=dang_giu, loai='dat_coc',
            trang_thai='thanh_cong').values_list('so_tien', flat=True)),
        'da_hoan_thang': sum(GiaoDich.objects.filter(loai='hoan_coc', ngay_tao__gte=dau_thang).values_list('so_tien', flat=True)),
    })


@nhan_vien_required
def ql_thu_coc(request, pk):
    """Thu cọc tại quầy (hoặc xác nhận cọc online) khi khách đến nhận máy."""
    don = get_object_or_404(ds_don(), pk=pk)
    if don.trang_thai != DonThue.DA_XAC_NHAN:
        messages.error(request, 'Đơn không ở trạng thái chờ nhận máy.')
        return redirect('ql_tien_coc')
    form = NhanCocForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = {'da_doi_chieu': True, 'da_thu_tien_thue': True, 'da_thu_coc': True,
                'phuong_thuc': form.cleaned_data['phuong_thuc'],
                'giao_thuc_te': timezone.now().replace(second=0, microsecond=0)}
        try:
            services.giao_may(pk, request.user, data)
            messages.success(request, f'{don.ma}: đã ghi nhận tiền cọc, khách đã nhận máy.')
            return redirect(reverse('ql_tien_coc') + '?tab=dang_giu')
        except ValidationError as exc:
            loi_form(form, exc)
    return render(request, 'quanly/thu_coc.html', {'don': don, 'form': form})


@nhan_vien_required
def ql_hoan_coc(request, pk):
    """Hoàn cọc khi khách trả máy: tự trừ phụ thu trả trễ, khấu trừ đền bù nếu máy hỏng (kèm ảnh)."""
    don = get_object_or_404(ds_don(), pk=pk)
    if don.trang_thai != DonThue.DANG_THUE or don.trang_thai_coc != DonThue.DA_THU:
        messages.error(request, 'Chỉ hoàn cọc cho đơn đang thuê và đã thu cọc.')
        return redirect('ql_tien_coc')
    bay_gio = timezone.localtime().replace(second=0, microsecond=0)
    form = HoanCocForm(request.POST or None, request.FILES or None, don=don,
                       initial={'tra_thuc_te': bay_gio, 'hinh_thuc_tra': don.hinh_thuc_tra or 'truc_tiep'})
    if request.method == 'POST' and form.is_valid():
        try:
            services.nhan_tra(pk, request.user, form.cleaned_data, anh_su_co=form.cleaned_data['anh_su_co'])
            messages.success(request, f'{don.ma}: đã hoàn cọc và hoàn tất đơn thuê.')
            return redirect(reverse('ql_tien_coc') + '?tab=da_hoan')
        except ValidationError as exc:
            loi_form(form, exc)
    phi_tre = tinh_phi_tra_tre(don.gio_tra, bay_gio)
    return render(request, 'quanly/hoan_coc.html', {'don': don, 'form': form, 'phi_tre': phi_tre,
        'so_gio_tre': max(math.ceil((timezone.now() - don.gio_tra).total_seconds() / 3600), 0),
        'hoan_du_kien': max(don.tien_coc - phi_tre, 0)})


@nhan_vien_required
def ql_chi_tiet_don(request, pk):
    return render(request, 'quanly/chi_tiet_don.html', {'don': get_object_or_404(ds_don(), pk=pk)})


@nhan_vien_required
@require_POST
def ql_huy_don(request, pk):
    """Hủy đơn đã xác nhận nhưng khách không đặt cọc (máy được trả lại lịch trống)."""
    get_object_or_404(DonThue, pk=pk)
    try:
        ly_do = request.POST.get('ly_do', '').strip() or 'Khách không đặt cọc để giữ lịch.'
        services.huy_yeu_cau(pk, ly_do)
        messages.success(request, 'Đã hủy đơn và trả máy về lịch trống.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('ql_chi_tiet_don', pk=pk)


@nhan_vien_required
@require_POST
def ql_phan_bo_lai(request, pk):
    get_object_or_404(DonThue, pk=pk)
    try:
        services.phan_bo_lai(pk)
        messages.success(request, 'Đã kiểm tra lại lịch và cập nhật phân bổ máy.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('ql_chi_tiet_don', pk=pk)


@nhan_vien_required
def ql_su_co(request):
    """Danh sách sự cố máy kèm ảnh tình trạng máy hỏng."""
    return render(request, 'quanly/su_co.html', {
        'ds_su_co': SuCo.objects.select_related('don', 'may__thiet_bi', 'nhan_vien').prefetch_related('cac_anh')})


@nhan_vien_required
def ql_bao_su_co(request, pk):
    """Báo sự cố cho một máy của đơn thuê và tải ảnh tình trạng máy."""
    don = get_object_or_404(ds_don(), pk=pk)
    form = BaoSuCoForm(request.POST or None, request.FILES or None, don=don)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            services.bao_su_co(pk, request.user, data['may'], data['loai'], data['mo_ta'], data['anh'])
            messages.success(request, 'Đã ghi nhận sự cố và lưu ảnh tình trạng máy.')
            return redirect('ql_chi_tiet_don', pk=pk)
        except ValidationError as exc:
            loi_form(form, exc)
    return render(request, 'quanly/bao_su_co.html', {'don': don, 'form': form})


@nhan_vien_required
def ql_xu_ly_su_co(request, pk):
    """Xem ảnh, tải thêm ảnh và cập nhật kết quả xử lý sự cố."""
    obj = get_object_or_404(SuCo.objects.select_related('don', 'may__thiet_bi'), pk=pk)
    form = SuCoForm(None, instance=obj)
    form_anh = ThemAnhSuCoForm()
    if request.method == 'POST' and 'tai_anh' in request.POST:
        form_anh = ThemAnhSuCoForm(request.POST, request.FILES)
        if form_anh.is_valid():
            for anh in form_anh.cleaned_data['anh']:
                AnhSuCo.objects.create(su_co=obj, anh=anh)
            messages.success(request, 'Đã tải thêm ảnh tình trạng máy.')
            return redirect('ql_xu_ly_su_co', pk=pk)
    elif request.method == 'POST':
        form = SuCoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã cập nhật xử lý sự cố.')
            return redirect('ql_su_co')
    return render(request, 'quanly/xu_ly_su_co.html', {'su_co': obj, 'form': form, 'form_anh': form_anh})


# ---------------------------------------------------------------------------
# Lịch máy (UC-1.3 kiểm tra máy trống, quản lý lịch)
# ---------------------------------------------------------------------------

@nhan_vien_required
def ql_lich(request):
    """Lịch tháng của từng dòng máy: mỗi ngày có số máy Trống, Đang thuê, Bảo trì."""
    ds_thiet_bi = list(ThietBi.objects.filter(ngung_cung_cap=False))
    thiet_bi = next((tb for tb in ds_thiet_bi if tb.ma == request.GET.get('may')), ds_thiet_bi[0] if ds_thiet_bi else None)
    lich, ngay_xem = None, None
    if thiet_bi:
        nam, thang = doc_thang(request.GET.get('thang'))
        lich = lich_thang(thiet_bi, nam, thang)
        ngay = request.GET.get('ngay', '')
        for tuan in lich['cac_tuan']:
            for o in tuan:
                if o and o['ngay'].isoformat() == ngay:
                    ngay_xem = o
    return render(request, 'quanly/lich.html', {'ds_thiet_bi': ds_thiet_bi, 'thiet_bi': thiet_bi,
                                              'lich': lich, 'ngay_xem': ngay_xem})


@chu_cua_hang_required
def ql_bao_cao(request):
    """Báo cáo doanh thu cho chủ cửa hàng: tính theo các đơn đã giao máy trong khoảng ngày chọn."""
    hom_nay = timezone.localdate()
    try:
        tu = date.fromisoformat(request.GET.get('tu') or hom_nay.replace(day=1).isoformat())
        den = date.fromisoformat(request.GET.get('den') or hom_nay.isoformat())
    except ValueError:
        messages.error(request, 'Ngày không hợp lệ. Đang hiển thị tháng hiện tại.')
        tu, den = hom_nay.replace(day=1), hom_nay
    if tu > den:
        messages.error(request, 'Ngày bắt đầu phải trước ngày kết thúc.')
        tu, den = den, tu
    ds = list(ds_don().filter(trang_thai__in=[DonThue.DANG_THUE, DonThue.HOAN_TAT],
                              giao_thuc_te__date__gte=tu, giao_thuc_te__date__lte=den).order_by('-giao_thuc_te'))
    theo_may = {}
    for don in ds:
        don.doanh_thu = don.tong_thanh_toan + don.phu_thu_tra_tre + don.khau_tru_den_bu
        for dong in don.cac_chi_tiet.all():
            muc = theo_may.setdefault(dong.thiet_bi.ten, {'ten': dong.thiet_bi.ten, 'so_luot': 0, 'tien_thue': 0})
            muc['so_luot'] += dong.so_luong
            muc['tien_thue'] += dong.thanh_tien
    return render(request, 'quanly/bao_cao.html', {
        'tu': tu, 'den': den, 'ds_don': ds,
        'tong_tien_thue': sum(d.tien_thue for d in ds), 'tong_giam_gia': sum(d.giam_gia for d in ds),
        'tong_phat_sinh': sum(d.phu_thu_tra_tre + d.khau_tru_den_bu for d in ds),
        'tong_doanh_thu': sum(d.doanh_thu for d in ds),
        'theo_may': sorted(theo_may.values(), key=lambda m: -m['tien_thue']),
    })

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Q
from django.db import IntegrityError, transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import chu_cua_hang_required
from .forms import DangKyForm, DangNhapForm, TaiKhoanForm
from .models import User


def dang_ky(request):
    """UC-6.1: Đăng ký tài khoản khách hàng."""
    form = DangKyForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        du_lieu = form.cleaned_data
        # Dùng email làm tên đăng nhập
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=du_lieu['email'], email=du_lieu['email'],
                    password=du_lieu['mat_khau'], ho_ten=du_lieu['ho_ten'], so_dien_thoai=du_lieu['so_dien_thoai'])
            login(request, user)
            messages.success(request, 'Đăng ký tài khoản thành công.')
            return redirect('trang_cua_toi')
        except IntegrityError:
            form.add_error(None, 'Email hoặc số điện thoại vừa được đăng ký. Vui lòng kiểm tra lại.')
    return render(request, 'accounts/dang_ky.html', {'form': form})


def dang_nhap(request):
    """UC-6.2: Đăng nhập và điều hướng theo vai trò."""
    form = DangNhapForm((request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        mat_khau = form.cleaned_data['mat_khau']
        tai_khoan = User.objects.filter(username=email).first()

        if tai_khoan is None:
            form.add_error('email', 'Tài khoản không tồn tại.')
        elif not tai_khoan.is_active:
            form.add_error(None, 'Tài khoản đã bị khóa, vui lòng liên hệ cửa hàng.')
        else:
            user = authenticate(request, username=email, password=mat_khau)
            if user is None:
                form.add_error(None, 'Email hoặc mật khẩu không chính xác.')
            else:
                login(request, user)
                # Nếu đang đặt thuê dở thì quay lại đúng trang đó
                trang_tiep = request.GET.get('next')
                if trang_tiep and url_has_allowed_host_and_scheme(trang_tiep,
                    allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(trang_tiep)
                # Mỗi vai trò vào trang chức năng riêng (có thanh điều hướng dọc)
                if user.la_nhan_vien:
                    return redirect('ql_tong_quan')
                return redirect('trang_cua_toi')
    return render(request, 'accounts/dang_nhap.html', {'form': form})


@require_POST
def dang_xuat(request):
    logout(request)
    return redirect('trang_chu')


@login_required
def tai_khoan(request):
    """UC-6.3: Xem và cập nhật thông tin tài khoản của mình."""
    form = TaiKhoanForm((request.POST if request.method == 'POST' else None), request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cập nhật thông tin thành công.')
        return redirect('tai_khoan')
    return render(request, 'accounts/tai_khoan.html', {'form': form})


@login_required
def doi_mat_khau(request):
    form = PasswordChangeForm(request.user, (request.POST if request.method == 'POST' else None))
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # giữ đăng nhập sau khi đổi
        messages.success(request, 'Đổi mật khẩu thành công.')
        return redirect('tai_khoan')
    return render(request, 'form_chung.html', {
        'form': form, 'tieu_de': 'Đổi mật khẩu', 'nut': 'Lưu mật khẩu',
        'url_huy': 'tai_khoan',
    })


@chu_cua_hang_required
def ql_tai_khoan(request):
    """UC-6.4: Danh sách tài khoản để phân quyền."""
    tu_khoa = request.GET.get('q', '')
    ds_tai_khoan = User.objects.order_by('vai_tro', 'ho_ten')
    if tu_khoa:
        ds_tai_khoan = ds_tai_khoan.filter(
            Q(ho_ten__icontains=tu_khoa) | Q(email__icontains=tu_khoa))
    return render(request, 'quanly/tai_khoan.html', {
        'ds_tai_khoan': ds_tai_khoan,
        'ds_vai_tro': User.VAI_TRO,
        'tu_khoa': tu_khoa,
    })


@chu_cua_hang_required
@require_POST
def ql_doi_vai_tro(request, pk):
    """UC-6.4: Đổi vai trò của một tài khoản."""
    tai_khoan = get_object_or_404(User, pk=pk)
    vai_tro_moi = request.POST.get('vai_tro')
    ds_hop_le = [ma for ma, ten in User.VAI_TRO]

    if tai_khoan == request.user:
        messages.error(request, 'Không thể tự đổi vai trò của chính mình.')
    elif vai_tro_moi not in ds_hop_le:
        messages.error(request, 'Vai trò không hợp lệ.')
    else:
        tai_khoan.vai_tro = vai_tro_moi
        tai_khoan.is_staff = vai_tro_moi == User.CHU_CUA_HANG
        tai_khoan.is_superuser = vai_tro_moi == User.CHU_CUA_HANG
        tai_khoan.save()
        messages.success(request, 'Cập nhật phân quyền thành công.')
    return redirect('ql_tai_khoan')


@chu_cua_hang_required
@require_POST
def ql_khoa_tai_khoan(request, pk):
    """UC-6.4: Khóa hoặc mở khóa tài khoản."""
    tai_khoan = get_object_or_404(User, pk=pk)
    if tai_khoan == request.user:
        messages.error(request, 'Không thể tự khóa tài khoản của chính mình.')
    else:
        tai_khoan.is_active = not tai_khoan.is_active
        tai_khoan.save()
        if tai_khoan.is_active:
            messages.success(request, 'Đã mở khóa tài khoản.')
        else:
            messages.success(request, 'Đã khóa tài khoản.')
    return redirect('ql_tai_khoan')

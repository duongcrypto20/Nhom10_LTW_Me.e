"""Các decorator kiểm tra quyền truy cập theo vai trò."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def nhan_vien_required(view_func):
    """Chỉ nhân viên và chủ cửa hàng mới được vào."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.la_nhan_vien:
            return render(request, 'khong_du_quyen.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def chu_cua_hang_required(view_func):
    """Chỉ chủ cửa hàng mới được vào."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.la_chu_cua_hang:
            return render(request, 'khong_du_quyen.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

def khach_hang_required(view_func):
    """Chỉ khách hàng mới được đặt thuê, gửi phản hồi."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.la_khach_hang:
            return render(request, 'khong_du_quyen.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

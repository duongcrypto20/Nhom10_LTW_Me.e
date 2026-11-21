"""
Các decorator kiểm tra quyền truy cập theo vai trò (UC-6.4).

Cách dùng:
    @nhan_vien_required
    def ql_tong_quan(request): ...

Người chưa đăng nhập được chuyển tới trang đăng nhập.
Người đã đăng nhập nhưng sai vai trò thấy trang "Không đủ quyền" (mã 403).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def yeu_cau_quyen(dieu_kien):
    """Tạo decorator: chỉ cho vào view khi dieu_kien(user) đúng."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not dieu_kien(request.user):
                return render(request, 'khong_du_quyen.html', status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Chỉ khách hàng: đặt thuê, đặt cọc, gửi phản hồi
khach_hang_required = yeu_cau_quyen(lambda user: user.la_khach_hang)

# Nhân viên và chủ cửa hàng: xử lý đơn, tiền cọc, thiết bị, phản hồi
nhan_vien_required = yeu_cau_quyen(lambda user: user.la_nhan_vien)

# Chỉ chủ cửa hàng: thêm thiết bị, gói, mã giảm giá, phân quyền, báo cáo doanh thu
chu_cua_hang_required = yeu_cau_quyen(lambda user: user.la_chu_cua_hang)

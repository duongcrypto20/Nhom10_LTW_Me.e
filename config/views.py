"""Các trang báo lỗi chung của dự án."""
from django.shortcuts import render


def loi_csrf(request, reason=''):
    """
    Hiện khi form gửi lên thiếu hoặc sai mã CSRF (mã chống giả mạo request).

    Thường gặp khi: mở trang quá lâu rồi mới bấm gửi, đã đăng xuất ở tab khác,
    hoặc trình duyệt chặn cookie. Người dùng chỉ cần tải lại trang và gửi lại.
    """
    return render(request, 'loi_csrf.html', status=403)

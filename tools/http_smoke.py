"""Kiểm tra website đang chạy bằng HTTP thật, gồm đăng nhập từng vai trò demo."""
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, Request

BASE = 'http://127.0.0.1:8000'


def check(opener, path):
    with opener.open(BASE + path, timeout=15) as response:
        if response.status != 200 or urlsplit(response.url).path != path:
            raise RuntimeError(f'{path}: unexpected response {response.status} {response.url}')
        response.read()
    print('OK', path)


public = build_opener()
for path in ['/', '/may-anh/', '/may-anh/m50/', '/goi-thue/', '/danh-gia/', '/quy-dinh/', '/hoi-dap/']:
    check(public, path)

for email, paths in [
    ('khach@demo.vn', ['/cua-toi/', '/gio-thue/', '/don-cua-toi/', '/feedback-cua-toi/', '/tai-khoan/dia-chi/', '/tai-khoan/', '/thong-bao/']),
    ('nv@demo.vn', ['/quan-ly/', '/quan-ly/yeu-cau/', '/quan-ly/giao-nhan/', '/quan-ly/giao-dich/', '/quan-ly/phan-hoi/', '/quan-ly/su-co/']),
    ('chu@demo.vn', ['/quan-ly/thiet-bi/', '/quan-ly/dich-vu/', '/quan-ly/ma-giam-gia/', '/quan-ly/danh-muc/', '/quan-ly/tai-khoan/', '/admin/']),
]:
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    opener.open(BASE + '/dang-nhap/', timeout=15).close()
    csrf = next(c.value for c in jar if c.name == 'csrftoken')
    request = Request(BASE + '/dang-nhap/', data=urlencode({'email': email, 'mat_khau': '123456',
        'csrfmiddlewaretoken': csrf}).encode(), headers={'Referer': BASE + '/dang-nhap/'})
    opener.open(request, timeout=15).close()
    for path in paths:
        check(opener, path)

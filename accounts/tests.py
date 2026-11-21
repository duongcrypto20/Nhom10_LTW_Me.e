"""
Kiểm thử app accounts: đăng nhập, cập nhật tài khoản, phân quyền và dữ liệu mẫu.

Chạy:  python manage.py test accounts
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from rentals.models import DonThue

from .models import User


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TaiKhoanTests(TestCase):
    def setUp(self):
        self.khach = User.objects.create_user(
            'khach@kiemtra.vn', email='khach@kiemtra.vn', password='123456',
            ho_ten='Khách kiểm tra', so_dien_thoai='0912345678',
        )
        self.chu = User.objects.create_user(
            'chu@kiemtra.vn', password='123456', ho_ten='Chủ', vai_tro=User.CHU_CUA_HANG,
        )

    def test_trung_so_dien_thoai_luc_luu_bao_loi_tren_form(self):
        self.client.force_login(self.khach)
        with patch('accounts.views.TaiKhoanForm.save', side_effect=IntegrityError):
            response = self.client.post(reverse('tai_khoan'), {
                'ho_ten': 'Khách kiểm tra', 'so_dien_thoai': '0987654321', 'cccd': '',
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('so_dien_thoai', response.context['form'].errors)

    def test_dang_nhap_khong_chuyen_toi_trang_ngoai(self):
        response = self.client.post(reverse('dang_nhap') + '?next=https://example.org/', {
            'email': self.khach.email, 'mat_khau': '123456',
        })
        self.assertRedirects(response, reverse('trang_cua_toi'))

    def test_khach_khong_tu_cap_quyen_chu(self):
        self.client.force_login(self.khach)
        response = self.client.post(reverse('ql_doi_vai_tro', args=[self.khach.pk]), {
            'vai_tro': User.CHU_CUA_HANG,
        })
        self.assertEqual(response.status_code, 403)
        self.khach.refresh_from_db()
        self.assertEqual(self.khach.vai_tro, User.KHACH_HANG)

    def test_doi_vai_tro_cap_va_thu_quyen_admin(self):
        self.client.force_login(self.chu)
        url = reverse('ql_doi_vai_tro', args=[self.khach.pk])

        self.client.post(url, {'vai_tro': User.CHU_CUA_HANG})
        self.khach.refresh_from_db()
        self.assertTrue(self.khach.is_superuser)

        self.client.post(url, {'vai_tro': User.NHAN_VIEN})
        self.khach.refresh_from_db()
        self.assertFalse(self.khach.is_staff)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DuLieuMauTests(TestCase):
    def test_chay_lai_lenh_tao_du_lieu_khong_bi_trung(self):
        call_command('taodulieu', stdout=StringIO())
        call_command('taodulieu', stdout=StringIO())

        self.assertEqual(User.objects.count(), 6)
        self.assertEqual(DonThue.objects.count(), 9)
        for email in ('khach@demo.com', 'nv@demo.com', 'chu@demo.com'):
            user = User.objects.get(username=email)
            self.assertTrue(user.check_password('123456'))

    def test_du_lieu_mau_co_du_cac_trang_thai_don(self):
        call_command('taodulieu', stdout=StringIO())
        trang_thai_co = set(DonThue.objects.values_list('trang_thai', flat=True))
        self.assertEqual(trang_thai_co, {ma for ma, ten in DonThue.TRANG_THAI})

    def test_dang_nhap_tai_khoan_demo_chuyen_dung_trang(self):
        call_command('taodulieu', stdout=StringIO())
        for email, trang in [('khach@demo.com', 'trang_cua_toi'), ('nv@demo.com', 'ql_tong_quan')]:
            self.client.logout()
            response = self.client.post(reverse('dang_nhap'), {'email': email, 'mat_khau': '123456'})
            self.assertRedirects(response, reverse(trang))


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BaoMatVaThongBaoLoiTests(TestCase):
    """Chống CSRF và thông báo lỗi tiếng Việt khi nhập sai."""

    def test_form_post_thieu_ma_csrf_bi_chan(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('dang_nhap'), {'email': 'a@b.com', 'mat_khau': '123456'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Không gửi được biểu mẫu', status_code=403)

    def test_form_post_co_ma_csrf_van_gui_duoc(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        trang = client.get(reverse('dang_nhap'))
        ma_csrf = trang.cookies['csrftoken'].value
        response = client.post(reverse('dang_nhap'), {
            'email': 'khong-co@demo.com', 'mat_khau': '123456', 'csrfmiddlewaretoken': ma_csrf,
        })
        self.assertEqual(response.status_code, 200)

    def test_dang_ky_sai_hien_loi_tung_o_va_tom_tat(self):
        response = self.client.post(reverse('dang_ky'), {
            'ho_ten': '', 'email': 'sai-email', 'so_dien_thoai': '12', 'mat_khau': '1', 'nhap_lai': '2',
        })
        loi = response.context['form'].errors
        self.assertEqual(loi['ho_ten'], ['Vui lòng nhập Họ tên.'])
        self.assertIn('không đúng định dạng', loi['email'][0])
        self.assertIn('ít nhất 6 ký tự', loi['mat_khau'][0])
        self.assertContains(response, 'Thông tin chưa hợp lệ')

    def test_dang_nhap_sai_mat_khau_bao_loi(self):
        User.objects.create_user('a@demo.com', email='a@demo.com', password='dung-mat-khau', ho_ten='A')
        response = self.client.post(reverse('dang_nhap'), {'email': 'a@demo.com', 'mat_khau': 'sai'})
        self.assertContains(response, 'Email hoặc mật khẩu không chính xác.')

"""Kiểm tra dữ liệu thiết bị trước khi dùng mã thiết bị trong đường dẫn."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .forms import ThietBiForm
from .models import LoaiThietBi, ThietBi


class ThietBiFormTests(TestCase):
    def setUp(self):
        self.danh_muc = LoaiThietBi.objects.create(ma='kiem-tra', ten='Máy kiểm tra')

    def du_lieu(self, ma):
        return {'ma': ma, 'ten': 'Canon kiểm tra', 'hang': 'Canon',
                'danh_muc': self.danh_muc.pk, 'gia_tri_den_bu': 0, 'tien_coc': 700000}

    def test_device_code_cannot_break_its_detail_url(self):
        form = ThietBiForm(self.du_lieu('canon/m50'))
        self.assertFalse(form.is_valid())
        self.assertIn('ma', form.errors)

    def test_device_code_is_normalized_before_save(self):
        form = ThietBiForm(self.du_lieu('CANON-M50'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().ma, 'canon-m50')


class DieuHuongChucNangTests(TestCase):
    def setUp(self):
        self.khach = User.objects.create_user('menu@example.com', ho_ten='Khách kiểm tra')
        self.may = ThietBi.objects.create(ma='may-kiem-tra', ten='Máy kiểm tra')
        self.cac_trang = [
            reverse('ds_may_anh'), reverse('chi_tiet_may_anh', args=[self.may.ma]),
            reverse('kiem_tra_lich'), reverse('goi_thue'),
            reverse('quy_dinh'), reverse('ds_danh_gia'),
        ]

    def test_da_dang_nhap_giu_sidebar_khi_chuyen_chuc_nang(self):
        self.client.force_login(self.khach)
        for url in self.cac_trang:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'base_app.html')
                self.assertContains(response, 'id="menu-app"')
                self.assertNotContains(response, 'id="menu-public"')

    def test_chua_dang_nhap_van_xem_duoc_trang_cong_khai(self):
        for url in self.cac_trang:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'base.html')
                self.assertContains(response, 'id="menu-public"')
                self.assertNotContains(response, 'id="menu-app"')

    def test_trang_chu_va_dang_nhap_dang_ky_giu_bo_cuc_rieng(self):
        self.client.force_login(self.khach)
        for ten in ('trang_chu', 'dang_nhap', 'dang_ky'):
            with self.subTest(trang=ten):
                response = self.client.get(reverse(ten))
                self.assertTemplateUsed(response, 'base.html')
                self.assertNotContains(response, 'id="menu-app"')

    def test_sidebar_cua_nhan_vien_va_chu_giu_dung_vai_tro(self):
        for vai_tro in (User.NHAN_VIEN, User.CHU_CUA_HANG):
            with self.subTest(vai_tro=vai_tro):
                user = User.objects.create_user(vai_tro, ho_ten=vai_tro, vai_tro=vai_tro)
                self.client.force_login(user)
                response = self.client.get(reverse('ds_may_anh'))
                self.assertTemplateUsed(response, 'base_app.html')
                self.assertContains(response, reverse('ql_tien_coc'))
                self.assertNotContains(response, 'Chọn máy và đặt thuê')

from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi
from . import services
from .forms import DatThueForm
from .models import BaoTri, DonThue, GiaoDich, PhanBoMay
from .utils import dem_may_trong, tinh_phi_tra_tre


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LuongThueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.khach = User.objects.create_user('khach@test.vn', email='khach@test.vn', password='123456', ho_ten='Khách', so_dien_thoai='0912345678')
        cls.khach2 = User.objects.create_user('khach2@test.vn', email='khach2@test.vn', password='123456', ho_ten='Khách hai')
        cls.nv = User.objects.create_user('nv@test.vn', password='123456', ho_ten='Nhân viên', vai_tro=User.NHAN_VIEN)
        cls.chu = User.objects.create_user('chu@test.vn', password='123456', ho_ten='Chủ', vai_tro=User.CHU_CUA_HANG, is_staff=True, is_superuser=True)
        cls.loai, _ = LoaiThietBi.objects.get_or_create(ma='mirrorless', defaults={'ten': 'Mirrorless'})
        cls.goi = GoiThue.objects.create(ten='6 giờ', so_gio_toi_da=6)
        cls.tb1 = ThietBi.objects.create(ma='m50', ten='Canon M50', hang='Canon', tien_coc=700000, danh_muc=cls.loai)
        cls.tb2 = ThietBi.objects.create(ma='xt20', ten='Fuji X-T20', hang='Fuji', tien_coc=1000000, danh_muc=cls.loai)
        for tb in (cls.tb1, cls.tb2):
            GiaThue.objects.create(thiet_bi=tb, goi_thue=cls.goi, gia=120000 if tb == cls.tb1 else 180000)
            for i in range(2):
                May.objects.create(thiet_bi=tb, so_seri=f'{tb.ma}-{i}')
        cls.voucher = MaGiamGia.objects.create(ma='TEST10', gia_tri=10, so_luot=2)

    def draft(self, items=None, voucher='', start=None):
        start = start or timezone.now() + timedelta(hours=2)
        return {'cac_muc': items or [{'thiet_bi_id': self.tb1.pk, 'so_luong': 1}],
            'ma_gui': str(uuid4()), 'goi_thue_id': self.goi.pk, 'gio_nhan': start.isoformat(),
            'gio_tra': (start + timedelta(hours=3)).isoformat(), 'ma_giam_gia': voucher, 'ghi_chu': ''}

    def order(self, multi=False, voucher=''):
        items = [{'thiet_bi_id': self.tb1.pk, 'so_luong': 2}, {'thiet_bi_id': self.tb2.pk, 'so_luong': 1}] if multi else None
        return services.luu_yeu_cau(self.khach, self.draft(items, voucher))

    def checks(self, don, damaged=False):
        return [dict(may=p.may, ben_ngoai='Nguyên vẹn', hoat_dong='Hoạt động tốt', thau_kinh='Sạch',
                     phu_kien='Pin, sạc, thẻ nhớ', co_hu_hong=damaged and i == 0)
                for i, p in enumerate(PhanBoMay.objects.filter(chi_tiet__don=don).select_related('may'))]

    def deliver(self, don):
        services.giao_may(don.pk, self.nv, dict(da_doi_chieu=True, da_thu_coc=True, da_thu_tien_thue=True,
            phuong_thuc='tien_mat', giao_thuc_te=timezone.now() - timedelta(minutes=2)), self.checks(don))

    def return_data(self, **kwargs):
        data = dict(tra_thuc_te=timezone.now(), hinh_thuc_tra='truc_tiep', da_xu_ly_tien=True,
            khau_tru_den_bu=0, phuong_thuc_hoan='tien_mat')
        data.update(kwargs)
        return data

    def test_multi_device_prices_and_deposits(self):
        don = self.order(multi=True, voucher='TEST10')
        self.assertEqual(don.tien_thue, 420000)
        self.assertEqual(don.tien_coc, 2400000)
        self.assertEqual(don.tong_thanh_toan, 378000)
        self.assertEqual(don.cac_chi_tiet.count(), 2)
        GiaThue.objects.all().update(gia=999000)
        don.refresh_from_db()
        self.assertEqual(don.tien_thue, 420000)

    def test_stale_draft_recalculates_price(self):
        tam = self.draft()
        GiaThue.objects.filter(thiet_bi=self.tb1).update(gia=150000)
        self.assertEqual(services.luu_yeu_cau(self.khach, tam).tien_thue, 150000)

    def test_duplicate_submit_creates_one_order_and_consumes_voucher_once(self):
        tam = self.draft(voucher='TEST10')
        a = services.luu_yeu_cau(self.khach, tam)
        b = services.luu_yeu_cau(self.khach, tam)
        self.assertEqual(a.pk, b.pk)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.so_luot, 1)

    def test_cancel_restores_voucher_once(self):
        don = self.order(voucher='TEST10')
        services.huy_yeu_cau(don.pk, 'Hủy', self.khach)
        with self.assertRaises(ValidationError):
            services.huy_yeu_cau(don.pk, 'Hủy lần hai', self.khach)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.so_luot, 2)

    def test_expired_voucher_rejected_at_submit(self):
        self.voucher.ngay_ket_thuc = timezone.now() - timedelta(days=1)
        self.voucher.save()
        with self.assertRaises(ValidationError):
            self.order(voucher='TEST10')
        self.assertEqual(DonThue.objects.count(), 0)

    def test_confirm_allocates_all_serial_numbers_and_blocks_overlap(self):
        don = self.order(multi=True)
        services.xac_nhan_lich(don.pk)
        self.assertEqual(PhanBoMay.objects.filter(chi_tiet__don=don).count(), 3)
        self.assertEqual(dem_may_trong(self.tb1, don.gio_nhan, don.gio_tra)[0], 0)
        with self.assertRaises(ValidationError):
            self.order()

    def test_confirmation_is_atomic_when_stock_changes(self):
        a = self.order(multi=True)
        b = self.order(multi=True)
        services.xac_nhan_lich(a.pk)
        with self.assertRaises(ValidationError):
            services.xac_nhan_lich(b.pk)
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, DonThue.CHO_XU_LY)
        self.assertFalse(PhanBoMay.objects.filter(chi_tiet__don=b).exists())

    def test_adjacent_bookings_do_not_overlap(self):
        a = self.order(multi=True)
        services.xac_nhan_lich(a.pk)
        b = services.luu_yeu_cau(self.khach, self.draft(start=a.gio_tra))
        services.xac_nhan_lich(b.pk)
        b.refresh_from_db()
        self.assertEqual(b.trang_thai, DonThue.DA_XAC_NHAN)

    def test_overdue_unreturned_device_stays_unavailable(self):
        don = self.order(multi=True)
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        DonThue.objects.filter(pk=don.pk).update(gio_tra=timezone.now() - timedelta(hours=1))
        self.assertEqual(dem_may_trong(self.tb1, timezone.now() + timedelta(days=1), timezone.now() + timedelta(days=2))[0], 0)

    def test_deposit_preconfirmation_is_not_collected_twice(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        services.dat_coc_online(don.pk, self.khach)
        self.deliver(don)
        deposits = don.cac_giao_dich.filter(loai='dat_coc', trang_thai='thanh_cong')
        self.assertEqual(deposits.count(), 2)
        self.assertEqual(deposits.get(phuong_thuc='online').so_tien, 50000)
        self.assertEqual(deposits.get(phuong_thuc='tien_mat').so_tien, 650000)
        self.assertEqual(don.tien_coc_da_thu, don.tien_coc)
        self.assertEqual(don.tien_coc_con_lai, 0)
        with self.assertRaises(ValidationError):
            self.deliver(don)
        self.assertEqual(don.cac_giao_dich.filter(loai='thanh_toan').count(), 1)

    def test_missing_inspections_roll_back_all_changes(self):
        don = self.order(multi=True)
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        with self.assertRaises(ValidationError):
            services.nhan_tra(don.pk, self.nv, self.return_data(), self.checks(don)[:1])
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DANG_THUE)
        self.assertFalse(don.cac_kiem_tra.filter(loai='tra').exists())

    def test_return_updates_each_device_independently(self):
        don = self.order(multi=True)
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        data = self.return_data(mo_ta_su_co='Thấu kính bị xước')
        data['khau_tru_den_bu'] = 200000
        services.nhan_tra(don.pk, self.nv, data, self.checks(don, damaged=True))
        don.refresh_from_db()
        self.assertEqual(don.hoan_lai, 2200000)
        self.assertEqual(May.objects.filter(tinh_trang=May.BAO_TRI).count(), 1)
        self.assertEqual(don.cac_su_co.count(), 1)
        self.assertEqual(don.cac_kiem_tra.count(), 6)
        with self.assertRaises(ValidationError):
            services.nhan_tra(don.pk, self.nv, data, self.checks(don))

    def test_cost_above_deposit_requires_supplemental_collection(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        data = self.return_data(mo_ta_su_co='Máy hỏng', da_xu_ly_tien=False)
        data['khau_tru_den_bu'] = 900000
        with self.assertRaises(ValidationError):
            services.nhan_tra(don.pk, self.nv, data, self.checks(don, True))
        data['da_xu_ly_tien'] = True
        services.nhan_tra(don.pk, self.nv, data, self.checks(don, True))
        self.assertEqual(don.cac_giao_dich.get(loai='phu_thu').so_tien, 200000)
        self.assertFalse(don.cac_giao_dich.filter(loai='hoan_coc').exists())

    def test_return_cannot_deduct_without_incident(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        data = self.return_data()
        data['khau_tru_den_bu'] = 100000
        with self.assertRaises(ValidationError):
            services.nhan_tra(don.pk, self.nv, data, self.checks(don))

    def test_online_deposit_holds_booking_and_notifies_customer(self):
        don = self.order()
        self.client.force_login(self.khach)
        # Đơn vừa đặt vào thẳng trang cọc, máy chưa được giữ cho tới khi cọc
        response = self.client.get(reverse('dat_coc', args=[don.pk]))
        self.assertContains(response, 'Thanh toán cọc lịch 50.000đ')
        self.assertNotContains(response, 'Website dùng cổng thanh toán mô phỏng')
        self.assertNotContains(response, 'Thanh toán cọc 700.000đ')
        self.assertFalse(PhanBoMay.objects.filter(chi_tiet__don=don).exists())
        self.client.post(reverse('dat_coc', args=[don.pk]), {})
        don.refresh_from_db()
        self.assertEqual(don.trang_thai_coc, DonThue.CHUA_THU)
        self.client.post(reverse('dat_coc', args=[don.pk]), {'dong_y': 'on'})
        self.client.post(reverse('dat_coc', args=[don.pk]), {'dong_y': 'on'})
        don.refresh_from_db()
        self.assertEqual((don.trang_thai, don.trang_thai_coc, don.hinh_thuc_coc), (DonThue.DA_XAC_NHAN, DonThue.DA_THU, 'online'))
        self.assertEqual(PhanBoMay.objects.filter(chi_tiet__don=don).count(), 1)
        gd = don.cac_giao_dich.get()
        self.assertEqual((gd.loai, gd.trang_thai, gd.so_tien), ('dat_coc', 'thanh_cong', 50000))
        self.assertEqual(don.tien_coc, 700000)
        self.assertEqual(don.tien_coc_con_lai, 650000)
        self.assertTrue(self.khach.cac_thong_bao.filter(tieu_de='Đặt cọc thành công').exists())
        self.assertContains(self.client.get(reverse('dat_coc', args=[don.pk])), 'Đặt cọc thành công')
        # Quy định: đã cọc thì không nhận hủy lịch
        self.client.post(reverse('huy_don', args=[don.pk]))
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_XAC_NHAN)
        self.client.force_login(self.khach2)
        self.assertEqual(self.client.get(reverse('dat_coc', args=[don.pk])).status_code, 404)

    def test_booking_deposit_is_once_per_order_and_qr_matches(self):
        from urllib.parse import parse_qs, urlsplit
        from .views import ma_qr_coc
        don = self.order(multi=True)
        with override_settings(THANH_TOAN={'ngan_hang': 'TEST', 'so_tai_khoan': '123456', 'chu_tai_khoan': 'TEST'}):
            self.assertEqual(parse_qs(urlsplit(ma_qr_coc(don)).query)['amount'], ['50000'])
        gd = services.dat_coc_online(don.pk, self.khach)
        self.assertEqual(gd.so_tien, 50000)
        self.assertEqual(don.tien_coc_con_lai, 2350000)

    def test_booking_deposit_can_display_original_bank_qr_image(self):
        from .views import ma_qr_coc
        don = self.order()
        bank = {'ngan_hang': 'MB', 'so_tai_khoan': '0357594008',
                'chu_tai_khoan': 'NGO QUYNH DUONG', 'anh_qr': 'img/qr-coc-lich.jpg'}
        self.client.force_login(self.khach)
        with override_settings(THANH_TOAN=bank):
            self.assertEqual(ma_qr_coc(don), '/static/img/qr-coc-lich.jpg')
            response = self.client.get(reverse('dat_coc', args=[don.pk]))
            self.assertContains(response, 'src="/static/img/qr-coc-lich.jpg"')
            self.assertContains(response, 'NGO QUYNH DUONG')
            self.assertContains(response, '0357594008')
            self.assertContains(response, '50.000đ')
            self.assertContains(response, f'COC {don.ma}')

    def test_partial_deposit_requires_balance_before_delivery_and_reports_real_funds(self):
        don = self.order()
        services.dat_coc_online(don.pk, self.khach)
        with self.assertRaises(ValidationError):
            services.giao_may(don.pk, self.nv, dict(da_doi_chieu=True, da_thu_tien_thue=True,
                giao_thuc_te=timezone.now() - timedelta(minutes=2)), self.checks(don))
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_XAC_NHAN)
        self.assertEqual(don.tien_coc_da_thu, 50000)
        self.client.force_login(self.nv)
        response = self.client.get(reverse('ql_thu_coc', args=[don.pk]))
        self.assertContains(response, '650.000đ')
        self.assertContains(response, '770.000đ')
        self.assertEqual(self.client.get(reverse('ql_tien_coc')).context['tong_dang_giu'], 50000)
        self.deliver(don)
        self.assertEqual(self.client.get(reverse('ql_tien_coc')).context['tong_dang_giu'], 700000)
        services.nhan_tra(don.pk, self.nv, self.return_data(), self.checks(don))
        self.assertEqual(don.cac_giao_dich.get(loai='hoan_coc').so_tien, 700000)

    def test_legacy_full_online_deposit_is_not_collected_again(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        GiaoDich.objects.create(don=don, loai='dat_coc', so_tien=700000, phuong_thuc='online')
        don.trang_thai_coc, don.hinh_thuc_coc = DonThue.DA_THU, 'online'
        don.save(update_fields=['trang_thai_coc', 'hinh_thuc_coc'])
        self.assertEqual(don.tien_coc_con_lai, 0)
        self.deliver(don)
        self.assertEqual(don.cac_giao_dich.filter(loai='dat_coc').count(), 1)

    def test_pending_and_rejected_deposits_do_not_reduce_balance(self):
        don = self.order()
        for state in ['cho_duyet', 'tu_choi']:
            GiaoDich.objects.create(don=don, loai='dat_coc', so_tien=700000,
                phuong_thuc='online', trang_thai=state)
        self.assertEqual(don.tien_coc_da_thu, 0)
        services.dat_coc_online(don.pk, self.khach)
        self.assertEqual(don.tien_coc_da_thu, 50000)
        self.assertEqual(don.tien_coc_con_lai, 650000)

    def test_deposit_fails_without_charge_when_devices_were_taken(self):
        cac_don = [self.order() for _ in range(3)]
        for don in cac_don[:2]:
            services.dat_coc_online(don.pk, self.khach)
        with self.assertRaises(ValidationError):
            services.dat_coc_online(cac_don[2].pk, self.khach)
        cac_don[2].refresh_from_db()
        self.assertEqual((cac_don[2].trang_thai, cac_don[2].trang_thai_coc), (DonThue.CHO_XU_LY, DonThue.CHUA_THU))
        self.assertFalse(cac_don[2].cac_giao_dich.exists())

    def test_unpaid_confirmed_order_can_be_cancelled_and_frees_device(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        nhan = timezone.now() + timedelta(hours=2, minutes=30)
        self.assertEqual(dem_may_trong(self.tb1, nhan, nhan + timedelta(hours=1))[0], 1)
        self.client.force_login(self.nv)
        self.client.post(reverse('ql_huy_don', args=[don.pk]), {'ly_do': 'Khách không cọc'})
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_HUY)
        self.assertEqual(dem_may_trong(self.tb1, nhan, nhan + timedelta(hours=1))[0], 2)

    def test_other_customer_cannot_access_order(self):
        don = self.order()
        self.client.force_login(self.khach2)
        self.assertEqual(self.client.get(reverse('chi_tiet_don', args=[don.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('ql_tong_quan')).status_code, 403)

    def test_late_fee_follows_shop_rule(self):
        han = timezone.now()
        self.assertEqual(tinh_phi_tra_tre(han, han + timedelta(minutes=10)), 0)
        self.assertEqual(tinh_phi_tra_tre(han, han + timedelta(minutes=15)), 50000)
        self.assertEqual(tinh_phi_tra_tre(han, han + timedelta(minutes=61)), 100000)
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        DonThue.objects.filter(pk=don.pk).update(gio_tra=timezone.now() - timedelta(minutes=90),
                                                 giao_thuc_te=timezone.now() - timedelta(hours=4))
        services.nhan_tra(don.pk, self.nv, self.return_data(), self.checks(don))
        don.refresh_from_db()
        self.assertEqual(don.phu_thu_tra_tre, 100000)
        self.assertEqual(don.hoan_lai, 600000)

    def test_calendar_shows_free_and_rented_devices(self):
        from .utils import lich_thang
        don = self.order()
        services.xac_nhan_lich(don.pk)
        ngay = timezone.localtime(don.gio_nhan).date()
        lich = lich_thang(self.tb1, ngay.year, ngay.month)
        o = next(o for tuan in lich['cac_tuan'] for o in tuan if o and o['ngay'] == ngay)
        self.assertEqual((len(o['trong']), len(o['dang_thue'])), (1, 1))
        self.assertEqual(o['dang_thue'][0]['don'], don)
        start = timezone.localtime(don.gio_nhan)
        tra = start + timedelta(hours=2)
        response = self.client.get(reverse('kiem_tra_lich'), {'thiet_bi': self.tb1.ma,
            'ngay_nhan': start.date().isoformat(), 'gio_nhan': start.strftime('%H:%M'),
            'ngay_tra': tra.date().isoformat(), 'gio_tra': tra.strftime('%H:%M')})
        self.assertContains(response, 'lich-tieu-de')
        self.assertContains(response, 'Trống, 1 trống, 1 đang thuê')
        self.assertContains(response, 'Còn 1/2 máy trống')
        # Thời gian đã qua thì báo lỗi, không hiện lịch
        response = self.client.get(reverse('kiem_tra_lich'), {'thiet_bi': self.tb1.ma, 'ngay_nhan': '2020-01-01',
            'gio_nhan': '09:00', 'ngay_tra': '2020-01-02', 'gio_tra': '09:00'})
        self.assertNotContains(response, 'lich-tieu-de')
        self.assertContains(response, 'phải ở tương lai')
        self.client.force_login(self.nv)
        response = self.client.get(reverse('ql_lich'), {'may': self.tb1.ma, 'thang': f'{ngay.year}-{ngay.month:02d}', 'ngay': ngay.isoformat()})
        self.assertContains(response, don.ma)

    def test_past_and_overlong_rental_are_rejected(self):
        data = {'goi_thue': self.goi.pk, 'gio_nhan': '2020-01-01T10:00', 'gio_tra': '2020-01-01T20:00'}
        form = DatThueForm(data, thiet_bi=self.tb1)
        self.assertFalse(form.is_valid())
        self.assertIn('gio_nhan', form.errors)
        self.assertIn('gio_tra', form.errors)

    def test_price_cell_can_be_removed_without_deleting_other_prices(self):
        self.client.force_login(self.nv)
        self.client.post(reverse('ql_dich_vu'), {f'gia_{self.tb1.pk}_{self.goi.pk}': ''})
        self.assertFalse(GiaThue.objects.filter(thiet_bi=self.tb1).exists())
        self.assertTrue(GiaThue.objects.filter(thiet_bi=self.tb2).exists())

    def test_role_changes_remove_django_admin_access(self):
        self.client.force_login(self.chu)
        self.client.post(reverse('ql_doi_vai_tro', args=[self.nv.pk]), {'vai_tro': User.CHU_CUA_HANG})
        self.nv.refresh_from_db()
        self.assertTrue(self.nv.is_superuser)
        self.client.post(reverse('ql_doi_vai_tro', args=[self.nv.pk]), {'vai_tro': User.NHAN_VIEN})
        self.nv.refresh_from_db()
        self.assertFalse(self.nv.is_staff)
        self.assertFalse(self.nv.is_superuser)

    def test_unsafe_login_redirect_is_rejected(self):
        response = self.client.post(reverse('dang_nhap') + '?next=https://outside.test/',
            {'email': self.khach.email, 'mat_khau': '123456'})
        self.assertRedirects(response, reverse('trang_cua_toi'))

    def test_all_public_customer_and_staff_pages_render(self):
        don = self.order(multi=True)
        public = ['trang_chu', 'ds_may_anh', 'goi_thue', 'quy_dinh', 'ds_danh_gia', 'dang_nhap', 'dang_ky']
        for name in public:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.client.force_login(self.khach)
        for name in ['trang_cua_toi', 'don_cua_toi', 'phan_hoi_cua_toi', 'tai_khoan', 'thong_bao']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('chi_tiet_don', args=[don.pk])).status_code, 200)
        self.client.force_login(self.chu)
        for name in ['ql_tong_quan', 'ql_yeu_cau', 'ql_kiem_tra_don', 'ql_tien_coc', 'ql_thiet_bi', 'ql_dich_vu', 'ql_ma_giam_gia', 'ql_su_co', 'ql_phan_hoi', 'ql_tai_khoan', 'ql_danh_muc', 'ql_lich', 'ql_bao_cao']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name in ['ql_xu_ly_yeu_cau', 'ql_chi_tiet_don']:
            self.assertEqual(self.client.get(reverse(name, args=[don.pk])).status_code, 200)
        services.xac_nhan_lich(don.pk)
        self.assertEqual(self.client.get(reverse('ql_thu_coc', args=[don.pk])).status_code, 200)
        self.client.force_login(self.khach)
        self.assertEqual(self.client.get(reverse('dat_coc', args=[don.pk])).status_code, 200)
        self.client.force_login(self.chu)
        self.deliver(don)
        self.assertEqual(self.client.get(reverse('ql_hoan_coc', args=[don.pk])).status_code, 200)

    def test_complete_booking_delivery_return_feedback_workflow(self):
        from feedback.models import DanhGia
        self.client.force_login(self.khach)
        start = timezone.localtime() + timedelta(hours=1)
        data = {'goi_thue': self.goi.pk, 'gio_nhan': start.strftime('%Y-%m-%dT%H:%M'),
            'gio_tra': (start + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'), 'so_luong': 2, 'ma_giam_gia': 'TEST10'}
        self.assertRedirects(self.client.post(reverse('dat_thue', args=[self.tb2.ma]), data), reverse('xac_nhan_dat_thue'))
        response = self.client.post(reverse('xac_nhan_dat_thue'))
        don = DonThue.objects.get()
        # Xác nhận đặt đơn thì chuyển thẳng sang trang thanh toán cọc
        self.assertRedirects(response, reverse('dat_coc', args=[don.pk]))
        self.assertEqual(don.cac_chi_tiet.get().so_luong, 2)
        self.client.post(reverse('dat_coc', args=[don.pk]), {'dong_y': 'on'})
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_XAC_NHAN)
        self.client.force_login(self.nv)
        # Quản lý tiền cọc: khách đã cọc online, nhân viên xác nhận khi khách nhận máy rồi hoàn cọc khi trả
        response = self.client.post(reverse('ql_thu_coc', args=[don.pk]), {'phuong_thuc': 'tien_mat', 'da_xac_nhan': 'on'})
        self.assertRedirects(response, reverse('ql_tien_coc') + '?tab=dang_giu')
        self.assertContains(self.client.get(reverse('ql_tien_coc')), don.ma)
        data = dict(hinh_thuc_tra='truc_tiep', khau_tru_den_bu=0, da_xu_ly_tien='on', phuong_thuc_hoan='tien_mat',
            tra_thuc_te=timezone.localtime().strftime('%Y-%m-%dT%H:%M'))
        self.assertRedirects(self.client.post(reverse('ql_hoan_coc', args=[don.pk]), data), reverse('ql_tien_coc') + '?tab=da_hoan')
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.HOAN_TAT)
        self.assertEqual(don.cac_giao_dich.get(loai='dat_coc', phuong_thuc='online').so_tien, 50000)
        self.assertEqual(don.tien_coc_da_thu, don.tien_coc)
        self.assertEqual(don.hoan_lai, don.tien_coc)
        self.client.force_login(self.khach)
        self.assertEqual(self.client.post(reverse('gui_danh_gia', args=[don.pk]), {'so_sao': 5, 'noi_dung': 'Máy dùng tốt, giao nhận thuận tiện.'}).status_code, 302)
        dg = DanhGia.objects.get()
        self.assertContains(self.client.get(reverse('ds_danh_gia')), 'Chờ xử lý')  # khách thấy đánh giá của mình
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('ds_danh_gia')), dg.noi_dung)
        self.client.force_login(self.nv)
        self.client.post(reverse('ql_doi_trang_thai_phan_hoi', args=[dg.pk]), {'hanh_dong': 'duyet'})
        self.client.post(reverse('ql_tra_loi_phan_hoi', args=[dg.pk]), {'tra_loi': 'Cảm ơn bạn đã sử dụng dịch vụ.'})
        response = self.client.get(reverse('ds_danh_gia'), {'thiet_bi': self.tb2.pk})
        self.assertContains(response, dg.noi_dung)
        self.assertContains(response, 'Cảm ơn bạn đã sử dụng dịch vụ.')
        response = self.client.get(reverse('ql_phan_hoi'), {'tu_ngay': '2026-02-02', 'den_ngay': '2026-01-01'})
        self.assertContains(response, 'Ngày kết thúc phải từ ngày bắt đầu trở đi.')

    def test_reallocate_broken_device_before_delivery(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        old = PhanBoMay.objects.get(chi_tiet__don=don).may
        old.tinh_trang = May.BAO_TRI
        old.save()
        with self.assertRaises(ValidationError):
            self.deliver(don)
        services.phan_bo_lai(don.pk)
        self.assertNotEqual(PhanBoMay.objects.get(chi_tiet__don=don).may_id, old.pk)
        self.deliver(don)

    def test_lost_device_cannot_be_booked_or_maintained(self):
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        data = self.return_data(mo_ta_su_co='Khách báo mất máy', loai_su_co='mat_may')
        data['khau_tru_den_bu'] = don.tien_coc
        services.nhan_tra(don.pk, self.nv, data, self.checks(don, True))
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        self.assertEqual(may.tinh_trang, May.MAT_MAY)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai_coc, DonThue.KHAU_TRU_TOAN_BO)

    def test_adjustment_does_not_consume_same_voucher_again(self):
        don = self.order(voucher='TEST10')
        services.huy_yeu_cau(don.pk, 'Đổi thời gian', dieu_chinh=True)
        services.luu_yeu_cau(self.khach, self.draft(voucher='TEST10'), don.pk)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.so_luot, 1)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.CHO_XU_LY)

    def test_empty_post_displays_required_field_errors(self):
        self.client.force_login(self.khach)
        response = self.client.post(reverse('dat_thue', args=[self.tb1.ma]), {})
        self.assertTrue(response.context['form'].errors)

    def availability_params(self, don=None, quantity=1):
        nhan = don.gio_nhan if don else timezone.now() + timedelta(days=2)
        tra = don.gio_tra if don else nhan + timedelta(hours=3)
        return {'gio_nhan': timezone.localtime(nhan).strftime('%Y-%m-%dT%H:%M'),
                'gio_tra': timezone.localtime(tra).strftime('%Y-%m-%dT%H:%M'), 'so_luong': quantity}

    def test_customers_can_check_stock_without_staff_access(self):
        don = self.order(multi=True)
        services.xac_nhan_lich(don.pk)
        params = self.availability_params(don)
        response = self.client.get(reverse('kiem_tra_may_trong', args=[self.tb1.ma]), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['so_may_trong'], 0)
        self.assertFalse(response.json()['du_may'])
        self.assertNotContains(response, self.khach.email)

    def test_stock_check_filters_broken_and_stopped_devices(self):
        May.objects.filter(thiet_bi=self.tb1).update(tinh_trang=May.BAO_TRI)
        response = self.client.get(reverse('kiem_tra_may_trong', args=[self.tb1.ma]), self.availability_params())
        self.assertEqual(response.json()['so_may_trong'], 0)
        self.tb2.ngung_cung_cap = True
        self.tb2.save()
        response = self.client.get(reverse('kiem_tra_may_trong', args=[self.tb2.ma]), self.availability_params())
        self.assertFalse(response.json()['du_may'])

    def test_stock_check_rejects_bad_dates_and_quantities(self):
        params = self.availability_params()
        params['gio_tra'] = params['gio_nhan']
        self.assertEqual(self.client.get(reverse('kiem_tra_may_trong', args=[self.tb1.ma]), params).status_code, 400)
        params = self.availability_params(quantity=-1)
        self.assertEqual(self.client.get(reverse('kiem_tra_may_trong', args=[self.tb1.ma]), params).status_code, 400)

    def test_checked_dates_and_quantity_are_carried_into_booking(self):
        self.client.force_login(self.khach)
        params = self.availability_params(quantity=2)
        response = self.client.get(reverse('kiem_tra_may_trong', args=[self.tb1.ma]), params)
        self.assertTrue(response.json()['du_may'])
        response = self.client.get(response.json()['dat_thue_url'])
        form = response.context['form']
        self.assertEqual(form.initial['so_luong'], 2)
        self.assertEqual(timezone.localtime(form.initial['gio_nhan']).strftime('%Y-%m-%dT%H:%M'), params['gio_nhan'])

    def test_custom_duration_uses_lowest_combination_and_freezes_quote(self):
        from catalog.pricing import bao_gia
        custom = GoiThue.objects.filter(tuy_chinh=True).first()
        day = GoiThue.objects.create(ten='1 ngày', so_gio_toi_da=23)
        two = GoiThue.objects.create(ten='2 ngày', so_gio_toi_da=47)
        GiaThue.objects.create(thiet_bi=self.tb1, goi_thue=day, gia=160000)
        GiaThue.objects.create(thiet_bi=self.tb1, goi_thue=two, gia=310000)
        tam = self.draft()
        tam['goi_thue_id'] = custom.pk
        start = timezone.now() + timedelta(days=2)
        tam['gio_nhan'], tam['gio_tra'] = start.isoformat(), (start + timedelta(hours=48)).isoformat()
        don = services.luu_yeu_cau(self.khach, tam)
        self.assertEqual(don.tien_thue, 430000)
        self.assertIn('Tùy chỉnh 48 giờ', don.cac_chi_tiet.get().cach_tinh_gia)
        GiaThue.objects.all().update(gia=1)
        don.refresh_from_db()
        self.assertEqual(don.tien_thue, 430000)

    def test_custom_package_does_not_require_fixed_price_row(self):
        custom = GoiThue.objects.filter(tuy_chinh=True).first()
        self.assertFalse(GiaThue.objects.filter(goi_thue=custom).exists())
        start = timezone.localtime() + timedelta(days=2)
        form = DatThueForm({'goi_thue': custom.pk, 'gio_nhan': start.strftime('%Y-%m-%dT%H:%M'),
            'gio_tra': (start + timedelta(hours=100)).strftime('%Y-%m-%dT%H:%M'),
            'so_luong': 1}, thiet_bi=self.tb1)
        self.assertTrue(form.is_valid(), form.errors)
        tam = self.draft()
        tam['goi_thue_id'] = custom.pk
        tam['tien_thue'] = 1
        self.assertEqual(services.luu_yeu_cau(self.khach, tam).tien_thue, 120000)

    def test_custom_quote_rejects_missing_rates(self):
        custom = GoiThue.objects.filter(tuy_chinh=True).first()
        GiaThue.objects.filter(thiet_bi=self.tb1).delete()
        tam = self.draft()
        tam['goi_thue_id'] = custom.pk
        with self.assertRaises(ValidationError):
            services.luu_yeu_cau(self.khach, tam)

    def test_feedback_hub_accepts_text_and_real_photo_then_publishes_after_approval(self):
        import io
        import tempfile
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from feedback.models import DanhGia
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.deliver(don)
        services.nhan_tra(don.pk, self.nv, self.return_data(), self.checks(don))
        self.client.force_login(self.khach)
        self.assertContains(self.client.get(reverse('phan_hoi_cua_toi')), reverse('gui_danh_gia', args=[don.pk]))
        image = io.BytesIO()
        Image.new('RGB', (20, 20), color='brown').save(image, format='PNG')
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            upload = SimpleUploadedFile('feedback.png', image.getvalue(), content_type='image/png')
            response = self.client.post(reverse('gui_danh_gia', args=[don.pk]),
                {'so_sao': 5, 'noi_dung': 'Máy chụp đẹp và giao nhận đúng giờ.', 'anh': upload})
            self.assertRedirects(response, reverse('ds_danh_gia') + '#danh-gia-cua-ban', fetch_redirect_response=False)
            dg = DanhGia.objects.get(don=don)
            self.assertTrue(dg.anh.storage.exists(dg.anh.name))
            self.assertContains(self.client.get(reverse('phan_hoi_cua_toi')), dg.anh.url)
            self.assertContains(self.client.get(reverse('ds_danh_gia')), dg.anh.url)  # mục Đánh giá của bạn
            self.client.logout()
            self.assertNotContains(self.client.get(reverse('ds_danh_gia')), dg.noi_dung)
            self.client.force_login(self.nv)
            self.client.post(reverse('ql_doi_trang_thai_phan_hoi', args=[dg.pk]), {'hanh_dong': 'duyet'})
            self.assertContains(self.client.get(reverse('ds_danh_gia')), dg.anh.url)
            self.assertContains(self.client.get(reverse('chi_tiet_may_anh', args=[self.tb1.ma])), dg.anh.url)

    def test_feedback_rejects_fake_image_and_foreign_order(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from feedback.models import DanhGia
        don = self.order()
        DonThue.objects.filter(pk=don.pk).update(trang_thai=DonThue.HOAN_TAT)
        self.client.force_login(self.khach2)
        self.assertEqual(self.client.post(reverse('gui_danh_gia', args=[don.pk]), {'so_sao': 5, 'noi_dung': 'Không phải đơn của tôi'}).status_code, 404)
        self.client.force_login(self.khach)
        response = self.client.post(reverse('gui_danh_gia', args=[don.pk]), {'so_sao': 5,
            'noi_dung': 'Máy dùng rất tốt.', 'anh': SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form_viet'].errors)
        self.assertFalse(DanhGia.objects.filter(don=don).exists())

    def anh_png(self, ten='may-hong.png'):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        Image.new('RGB', (16, 16), color='gray').save(buf, format='PNG')
        return SimpleUploadedFile(ten, buf.getvalue(), content_type='image/png')

    def test_deposit_pages_damage_photos_and_order_lookup(self):
        import tempfile
        from .models import AnhSuCo, SuCo
        don = self.order()
        services.xac_nhan_lich(don.pk)
        self.client.force_login(self.nv)
        # Kiểm tra thông tin đơn thuê theo mã đơn
        response = self.client.get(reverse('ql_kiem_tra_don'), {'q': don.ma})
        self.assertContains(response, don.ma)
        # Đơn chưa cọc nằm ở mục Chưa thu cọc, thu cọc tại quầy
        self.assertContains(self.client.get(reverse('ql_tien_coc'), {'tab': 'chua_thu'}), don.ma)
        self.client.post(reverse('ql_thu_coc', args=[don.pk]), {'phuong_thuc': 'chuyen_khoan', 'da_xac_nhan': 'on'})
        don.refresh_from_db()
        self.assertEqual((don.trang_thai, don.trang_thai_coc, don.hinh_thuc_coc), (DonThue.DANG_THUE, DonThue.DA_THU, 'chuyen_khoan'))
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        data = dict(hinh_thuc_tra='truc_tiep', khau_tru_den_bu=200000, da_xu_ly_tien='on', phuong_thuc_hoan='tien_mat',
            tra_thuc_te=timezone.localtime().strftime('%Y-%m-%dT%H:%M'), may_hu_hong=[may.pk],
            loai_su_co='hu_hong', mo_ta_su_co='Màn hình bị nứt góc trái')
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            # Máy hỏng mà không có ảnh thì không cho hoàn cọc
            response = self.client.post(reverse('ql_hoan_coc', args=[don.pk]), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn('anh_su_co', response.context['form'].errors)
            data['anh_su_co'] = [self.anh_png('1.png'), self.anh_png('2.png')]
            self.assertEqual(self.client.post(reverse('ql_hoan_coc', args=[don.pk]), data).status_code, 302)
            don.refresh_from_db()
            may.refresh_from_db()
            self.assertEqual(don.trang_thai, DonThue.HOAN_TAT)
            self.assertEqual(don.hoan_lai, don.tien_coc - 200000)
            self.assertEqual(may.tinh_trang, May.BAO_TRI)
            su_co = SuCo.objects.get(don=don)
            self.assertEqual(su_co.cac_anh.count(), 2)
            self.assertContains(self.client.get(reverse('ql_su_co')), su_co.cac_anh.first().anh.url)
            # Báo thêm sự cố từ trang đơn, bắt buộc có ảnh
            self.assertEqual(self.client.post(reverse('ql_bao_su_co', args=[don.pk]),
                {'may': may.pk, 'loai': 'thieu_phu_kien', 'mo_ta': 'Thiếu sạc'}).status_code, 200)
            self.client.post(reverse('ql_bao_su_co', args=[don.pk]),
                {'may': may.pk, 'loai': 'thieu_phu_kien', 'mo_ta': 'Thiếu sạc', 'anh': self.anh_png()})
            self.assertEqual(SuCo.objects.filter(don=don).count(), 2)
            self.assertEqual(AnhSuCo.objects.count(), 3)
            # Khách thấy ảnh sự cố trong chi tiết đơn của mình
            self.client.force_login(self.khach)
            self.assertContains(self.client.get(reverse('chi_tiet_don', args=[don.pk])), su_co.cac_anh.first().anh.url)

    def test_review_page_composer_gallery_and_own_reviews(self):
        from feedback.models import DanhGia
        don = self.order()
        don_chua_xong = self.order()
        DonThue.objects.filter(pk=don.pk).update(trang_thai=DonThue.HOAN_TAT)
        # Khách chưa đăng nhập: thấy ảnh feedback và ô mời đăng nhập, không có form
        response = self.client.get(reverse('ds_danh_gia'))
        self.assertContains(response, 'img/feedback/')
        self.assertContains(response, 'đăng nhập để viết đánh giá')
        self.assertNotContains(response, 'id="sao-5"')
        self.assertEqual(self.client.post(reverse('ds_danh_gia'), {'so_sao': 5}).status_code, 302)
        # Khách: ô viết đánh giá chỉ cho chọn đơn đã hoàn tất
        self.client.force_login(self.khach)
        response = self.client.get(reverse('ds_danh_gia'))
        self.assertContains(response, 'id="viet-danh-gia"')
        self.assertEqual(list(response.context['form_viet'].fields['don'].queryset), [don])
        response = self.client.post(reverse('ds_danh_gia'), {'don': don_chua_xong.pk, 'so_sao': 4, 'noi_dung': 'Đơn chưa xong'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('don', response.context['form_viet'].errors)
        response = self.client.post(reverse('ds_danh_gia'), {'don': don.pk, 'so_sao': 4, 'noi_dung': 'Máy nhẹ, pin bền.'})
        self.assertRedirects(response, reverse('ds_danh_gia') + '#danh-gia-cua-ban', fetch_redirect_response=False)
        self.assertEqual(DanhGia.objects.get(don=don).so_sao, 4)
        response = self.client.get(reverse('ds_danh_gia'))
        self.assertContains(response, 'Máy nhẹ, pin bền.')
        self.assertEqual(list(response.context['form_viet'].fields['don'].queryset), [])

"""
Kiểm thử app rentals: đặt thuê, giữ máy, đặt cọc, thu cọc khi nhận máy, hoàn cọc khi trả máy.

Chạy:  python manage.py test rentals
"""
import tempfile
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

from . import services
from .models import DonThue, GiaoDich, PhanBoMay, SuCo
from .utils import dem_may_trong, tinh_phi_tra_tre


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CoSoTest(TestCase):
    """Dữ liệu dùng chung: 3 vai trò, 2 dòng máy (mỗi dòng 2 máy), 1 gói 6 giờ, 1 mã giảm giá."""

    @classmethod
    def setUpTestData(cls):
        cls.khach = User.objects.create_user(
            'khach@test.vn', email='khach@test.vn', password='123456',
            ho_ten='Khách', so_dien_thoai='0912345678',
        )
        cls.khach2 = User.objects.create_user('khach2@test.vn', password='123456', ho_ten='Khách hai')
        cls.nv = User.objects.create_user('nv@test.vn', password='123456', ho_ten='Nhân viên',
                                          vai_tro=User.NHAN_VIEN)
        cls.chu = User.objects.create_user('chu@test.vn', password='123456', ho_ten='Chủ',
                                           vai_tro=User.CHU_CUA_HANG, is_staff=True, is_superuser=True)

        loai = LoaiThietBi.objects.create(ma='mirrorless', ten='Mirrorless')
        cls.goi = GoiThue.objects.create(ten='6 giờ', so_gio_toi_da=6)
        cls.tb1 = ThietBi.objects.create(ma='m50', ten='Canon M50', hang='Canon',
                                         tien_coc=700_000, danh_muc=loai)
        cls.tb2 = ThietBi.objects.create(ma='xt20', ten='Fuji X-T20', hang='Fuji',
                                         tien_coc=1_000_000, danh_muc=loai)
        GiaThue.objects.create(thiet_bi=cls.tb1, goi_thue=cls.goi, gia=120_000)
        GiaThue.objects.create(thiet_bi=cls.tb2, goi_thue=cls.goi, gia=180_000)
        for thiet_bi in (cls.tb1, cls.tb2):
            for i in range(2):
                May.objects.create(thiet_bi=thiet_bi, so_seri=f'{thiet_bi.ma}-{i}')
        cls.voucher = MaGiamGia.objects.create(ma='TEST10', gia_tri=10, so_luot=2)

    # ----- Hàm tạo dữ liệu nhanh -----

    def ban_nhap(self, cac_muc=None, ma_giam_gia='', bat_dau=None):
        bat_dau = bat_dau or timezone.now() + timedelta(hours=2)
        return {
            'cac_muc': cac_muc or [{'thiet_bi_id': self.tb1.pk, 'so_luong': 1}],
            'ma_gui': str(uuid4()),
            'goi_thue_id': self.goi.pk,
            'gio_nhan': bat_dau.isoformat(),
            'gio_tra': (bat_dau + timedelta(hours=3)).isoformat(),
            'ma_giam_gia': ma_giam_gia,
            'ghi_chu': '',
        }

    def tao_don(self, nhieu_may=False, ma_giam_gia='', khach=None):
        cac_muc = None
        if nhieu_may:
            cac_muc = [
                {'thiet_bi_id': self.tb1.pk, 'so_luong': 2},
                {'thiet_bi_id': self.tb2.pk, 'so_luong': 1},
            ]
        return services.luu_yeu_cau(khach or self.khach, self.ban_nhap(cac_muc, ma_giam_gia))

    def giao_may(self, don):
        """Đưa đơn qua bước giữ máy và khách nhận máy."""
        don.refresh_from_db()
        if don.trang_thai == DonThue.CHO_XU_LY:
            services.xac_nhan_lich(don.pk)
        services.thu_coc_khi_nhan_may(
            don.pk, self.nv, 'tien_mat', gio_giao=timezone.now() - timedelta(minutes=2),
        )

    def hoan_coc(self, don, **thong_tin):
        du_lieu = dict(tra_thuc_te=timezone.now(), hinh_thuc_tra='truc_tiep', phuong_thuc='tien_mat')
        du_lieu.update(thong_tin)
        services.hoan_coc_khi_tra_may(don.pk, self.nv, **du_lieu)


class DatThueTests(CoSoTest):
    """UC-1.1, UC-1.2: lập báo giá và lưu đơn."""

    def test_don_nhieu_may_tinh_dung_tien_thue_va_coc(self):
        don = self.tao_don(nhieu_may=True)
        self.assertEqual(don.tien_thue, 2 * 120_000 + 180_000)
        self.assertEqual(don.tien_coc, 2 * 700_000 + 1_000_000)
        self.assertEqual(don.cac_chi_tiet.count(), 2)

    def test_bam_gui_hai_lan_chi_tao_mot_don_va_tru_mot_luot_ma(self):
        tam = self.ban_nhap(ma_giam_gia='TEST10')
        services.luu_yeu_cau(self.khach, tam)
        services.luu_yeu_cau(self.khach, tam)
        self.voucher.refresh_from_db()
        self.assertEqual(DonThue.objects.count(), 1)
        self.assertEqual(self.voucher.so_luot, 1)

    def test_huy_don_tra_lai_luot_ma_giam_gia(self):
        don = self.tao_don(ma_giam_gia='TEST10')
        services.huy_yeu_cau(don.pk, 'Khách hủy', khach_hang=self.khach)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.so_luot, 2)

    def test_gio_nhan_trong_qua_khu_bi_tu_choi(self):
        tam = self.ban_nhap(bat_dau=timezone.now() - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            services.kiem_tra_ban_nhap(tam)

    def test_luong_day_du_tu_dat_thue_den_hoan_coc_qua_giao_dien(self):
        # Khách đặt thuê 2 máy X-T20 và dùng mã giảm giá
        self.client.force_login(self.khach)
        bat_dau = timezone.localtime() + timedelta(hours=1)
        response = self.client.post(reverse('dat_thue', args=[self.tb2.ma]), {
            'goi_thue': self.goi.pk,
            'gio_nhan': bat_dau.strftime('%Y-%m-%dT%H:%M'),
            'gio_tra': (bat_dau + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M'),
            'so_luong': 2,
            'ma_giam_gia': 'TEST10',
        })
        self.assertRedirects(response, reverse('xac_nhan_dat_thue'))

        # Xác nhận đặt đơn thì chuyển thẳng sang trang đặt cọc
        response = self.client.post(reverse('xac_nhan_dat_thue'))
        don = DonThue.objects.get()
        self.assertRedirects(response, reverse('dat_coc', args=[don.pk]))

        # Khách cọc lịch online, hệ thống giữ máy
        self.client.post(reverse('dat_coc', args=[don.pk]), {'dong_y': 'on'})
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_XAC_NHAN)
        self.assertEqual(don.trang_thai_coc, DonThue.DA_THU)

        # Nhân viên thu cọc khi khách nhận máy
        self.client.force_login(self.nv)
        response = self.client.post(reverse('ql_thu_coc', args=[don.pk]), {
            'phuong_thuc': 'tien_mat', 'da_xac_nhan': 'on',
        })
        self.assertRedirects(response, reverse('ql_tien_coc') + '?tab=dang_giu')

        # Nhân viên hoàn cọc khi khách trả máy
        response = self.client.post(reverse('ql_hoan_coc', args=[don.pk]), {
            'hinh_thuc_tra': 'truc_tiep',
            'tra_thuc_te': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'khau_tru_den_bu': 0,
            'phuong_thuc': 'tien_mat',
            'da_xu_ly_tien': 'on',
        })
        self.assertRedirects(response, reverse('ql_tien_coc') + '?tab=da_hoan')
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.HOAN_TAT)
        self.assertEqual(don.hoan_lai, 2_000_000)


class GiuMayTests(CoSoTest):
    """UC-1.3, UC-1.4: kiểm tra máy trống, giữ máy, đổi máy."""

    def test_xac_nhan_giu_du_so_may_va_chan_don_trung_lich(self):
        don = self.tao_don(nhieu_may=True)
        services.xac_nhan_lich(don.pk)
        self.assertEqual(PhanBoMay.objects.filter(chi_tiet__don=don).count(), 3)

        # Dòng M50 đã hết máy trong khung giờ này
        with self.assertRaises(ValidationError):
            self.tao_don(khach=self.khach2)

    def test_hai_don_noi_tiep_nhau_khong_bi_trung(self):
        don_1 = self.tao_don()
        services.xac_nhan_lich(don_1.pk)
        gio_bat_dau_sau = don_1.gio_tra
        so_trong, _ = dem_may_trong(self.tb1, gio_bat_dau_sau, gio_bat_dau_sau + timedelta(hours=2))
        self.assertEqual(so_trong, 2)

    def test_may_qua_han_chua_tra_van_bi_giu(self):
        don = self.tao_don()
        self.giao_may(don)
        DonThue.objects.filter(pk=don.pk).update(gio_tra=timezone.now() - timedelta(hours=1))
        so_trong, _ = dem_may_trong(self.tb1, timezone.now() + timedelta(days=1),
                                    timezone.now() + timedelta(days=2))
        self.assertEqual(so_trong, 1)

    def test_doi_may_khac_cung_dong(self):
        don = self.tao_don()
        services.xac_nhan_lich(don.pk)
        may_cu = PhanBoMay.objects.get(chi_tiet__don=don).may
        may_cu.tinh_trang = May.BAO_TRI
        may_cu.save()

        services.phan_bo_lai(don.pk)
        may_moi = PhanBoMay.objects.get(chi_tiet__don=don).may
        self.assertNotEqual(may_cu, may_moi)

    def test_huy_don_chua_coc_tra_may_ve_lich_trong(self):
        don = self.tao_don()
        services.xac_nhan_lich(don.pk)
        services.huy_yeu_cau(don.pk, 'Khách không cọc')
        so_trong, _ = dem_may_trong(self.tb1, don.gio_nhan, don.gio_tra)
        self.assertEqual(so_trong, 2)


class TienCocTests(CoSoTest):
    """Tiền cọc: cọc lịch online, thu cọc khi nhận máy, hoàn cọc khi trả máy."""

    def test_coc_lich_online_giu_may_va_bao_khach(self):
        don = self.tao_don()
        services.dat_coc_online(don.pk, self.khach)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, DonThue.DA_XAC_NHAN)
        self.assertEqual(don.tien_coc_da_thu, DonThue.COC_GIU_LICH)
        self.assertEqual(don.tien_coc_con_lai, 700_000 - DonThue.COC_GIU_LICH)
        self.assertTrue(self.khach.cac_thong_bao.filter(tieu_de='Đặt cọc thành công').exists())

    def test_khong_coc_hai_lan(self):
        don = self.tao_don()
        services.dat_coc_online(don.pk, self.khach)
        with self.assertRaises(ValidationError):
            services.dat_coc_online(don.pk, self.khach)

    def test_khach_khac_khong_duoc_coc_ho(self):
        don = self.tao_don()
        with self.assertRaises(ValidationError):
            services.dat_coc_online(don.pk, self.khach2)

    def test_het_may_thi_khong_ghi_nhan_coc(self):
        don = self.tao_don()
        May.objects.filter(thiet_bi=self.tb1).update(tinh_trang=May.BAO_TRI)
        with self.assertRaises(ValidationError):
            services.dat_coc_online(don.pk, self.khach)
        self.assertFalse(GiaoDich.objects.exists())

    def test_nhan_may_thu_phan_coc_con_lai_va_tien_thue(self):
        don = self.tao_don()
        services.dat_coc_online(don.pk, self.khach)
        self.giao_may(don)
        don.refresh_from_db()

        self.assertEqual(don.trang_thai, DonThue.DANG_THUE)
        self.assertEqual(don.tien_coc_da_thu, 700_000)
        self.assertTrue(don.cac_giao_dich.filter(loai=GiaoDich.THANH_TOAN, so_tien=120_000).exists())
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        self.assertEqual(may.tinh_trang, May.DANG_THUE)

    def test_tra_dung_gio_hoan_du_coc(self):
        don = self.tao_don()
        self.giao_may(don)
        self.hoan_coc(don)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai_coc, DonThue.DA_HOAN)
        self.assertEqual(don.hoan_lai, 700_000)
        self.assertEqual(PhanBoMay.objects.get(chi_tiet__don=don).may.tinh_trang, May.SAN_SANG)

    def test_may_hu_hong_bi_khau_tru_va_chuyen_bao_tri(self):
        don = self.tao_don()
        self.giao_may(don)
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        self.hoan_coc(don, may_hu_hong=[may], mo_ta_hu_hong='Trầy màn hình', khau_tru_den_bu=200_000)

        don.refresh_from_db()
        may.refresh_from_db()
        self.assertEqual(don.hoan_lai, 500_000)
        self.assertEqual(don.trang_thai_coc, DonThue.HOAN_MOT_PHAN)
        self.assertEqual(may.tinh_trang, May.BAO_TRI)

    def test_den_bu_vuot_coc_thi_thu_them(self):
        don = self.tao_don()
        self.giao_may(don)
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        self.hoan_coc(don, may_hu_hong=[may], mo_ta_hu_hong='Vỡ ống kính', khau_tru_den_bu=900_000)

        don.refresh_from_db()
        self.assertEqual(don.trang_thai_coc, DonThue.KHAU_TRU_TOAN_BO)
        self.assertEqual(don.can_thu_them, 200_000)
        self.assertTrue(don.cac_giao_dich.filter(loai=GiaoDich.PHU_THU, so_tien=200_000).exists())

    def test_khong_khau_tru_khi_khong_co_may_hong(self):
        don = self.tao_don()
        self.giao_may(don)
        with self.assertRaises(ValidationError):
            self.hoan_coc(don, khau_tru_den_bu=100_000)

    def test_phu_thu_tra_tre_theo_quy_dinh(self):
        han_tra = timezone.now()
        self.assertEqual(tinh_phi_tra_tre(han_tra, han_tra + timedelta(minutes=14)), 0)
        self.assertEqual(tinh_phi_tra_tre(han_tra, han_tra + timedelta(minutes=15)), 50_000)
        self.assertEqual(tinh_phi_tra_tre(han_tra, han_tra + timedelta(minutes=61)), 100_000)


class GiaoDienTests(CoSoTest):
    """Mọi trang mở được với đúng vai trò; sai vai trò bị chặn."""

    def test_cac_trang_mo_duoc(self):
        don = self.tao_don(nhieu_may=True)

        for ten in ['trang_chu', 'ds_may_anh', 'goi_thue', 'quy_dinh', 'ds_danh_gia', 'kiem_tra_lich']:
            with self.subTest(trang=ten):
                self.assertEqual(self.client.get(reverse(ten)).status_code, 200)

        self.client.force_login(self.khach)
        for ten in ['trang_cua_toi', 'don_cua_toi', 'phan_hoi_cua_toi', 'tai_khoan', 'thong_bao']:
            with self.subTest(trang=ten):
                self.assertEqual(self.client.get(reverse(ten)).status_code, 200)
        self.assertEqual(self.client.get(reverse('chi_tiet_don', args=[don.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('dat_coc', args=[don.pk])).status_code, 200)

        self.client.force_login(self.chu)
        for ten in ['ql_tong_quan', 'ql_yeu_cau', 'ql_tien_coc', 'ql_lich', 'ql_bao_cao', 'ql_thiet_bi',
                    'ql_dich_vu', 'ql_ma_giam_gia', 'ql_danh_muc', 'ql_phan_hoi', 'ql_tai_khoan']:
            with self.subTest(trang=ten):
                self.assertEqual(self.client.get(reverse(ten)).status_code, 200)
        for ten in ['ql_xu_ly_yeu_cau', 'ql_chi_tiet_don']:
            self.assertEqual(self.client.get(reverse(ten, args=[don.pk])).status_code, 200)

        services.xac_nhan_lich(don.pk)
        self.assertEqual(self.client.get(reverse('ql_thu_coc', args=[don.pk])).status_code, 200)
        self.giao_may(don)
        self.assertEqual(self.client.get(reverse('ql_hoan_coc', args=[don.pk])).status_code, 200)

    def test_khach_khac_khong_xem_duoc_don(self):
        don = self.tao_don()
        self.client.force_login(self.khach2)
        self.assertEqual(self.client.get(reverse('chi_tiet_don', args=[don.pk])).status_code, 404)

    def test_khach_khong_vao_duoc_khu_quan_ly(self):
        self.client.force_login(self.khach)
        self.assertEqual(self.client.get(reverse('ql_tien_coc')).status_code, 403)

    def test_tim_don_theo_ma_o_trang_tien_coc(self):
        don = self.tao_don()
        services.dat_coc_online(don.pk, self.khach)
        self.client.force_login(self.nv)
        response = self.client.get(reverse('ql_tien_coc'), {'tab': 'dang_giu', 'q': don.ma})
        self.assertContains(response, don.ma)


def tao_anh_png(ten='hong.png'):
    """Tạo một ảnh PNG nhỏ thật trong bộ nhớ để thử chức năng tải ảnh."""
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    bo_dem = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(bo_dem, 'PNG')
    return SimpleUploadedFile(ten, bo_dem.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SuCoTests(CoSoTest):
    """Nhân viên ghi nhận sự cố: mức độ, mô tả, ảnh máy hỏng."""

    def don_dang_thue(self):
        don = self.tao_don()
        self.giao_may(don)
        return don, PhanBoMay.objects.get(chi_tiet__don=don).may

    def test_ghi_nhan_su_co_kem_nhieu_anh(self):
        don, may = self.don_dang_thue()
        self.client.force_login(self.nv)
        response = self.client.post(reverse('ql_ghi_nhan_su_co', args=[don.pk]), {
            'may': may.pk,
            'muc_do': SuCo.NHE,
            'mo_ta': 'Trầy nhẹ ở viền màn hình',
            'anh': [tao_anh_png('a.png'), tao_anh_png('b.png')],
        })
        su_co = SuCo.objects.get()
        self.assertRedirects(response, reverse('ql_chi_tiet_su_co', args=[su_co.pk]))
        self.assertEqual(su_co.cac_anh.count(), 2)
        self.assertContains(self.client.get(reverse('ql_su_co')), su_co.cac_anh.first().anh.url)

    def test_bat_buoc_co_anh_va_mo_ta(self):
        don, may = self.don_dang_thue()
        self.client.force_login(self.nv)
        response = self.client.post(reverse('ql_ghi_nhan_su_co', args=[don.pk]), {
            'may': may.pk, 'muc_do': SuCo.NANG, 'mo_ta': 'hỏng',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('anh', response.context['form'].errors)
        self.assertIn('mo_ta', response.context['form'].errors)
        self.assertFalse(SuCo.objects.exists())

    def test_file_khong_phai_anh_bi_tu_choi(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        don, may = self.don_dang_thue()
        self.client.force_login(self.nv)
        response = self.client.post(reverse('ql_ghi_nhan_su_co', args=[don.pk]), {
            'may': may.pk, 'muc_do': SuCo.NHE, 'mo_ta': 'Trầy nhẹ ở viền màn hình',
            'anh': SimpleUploadedFile('gia.png', b'khong phai anh', content_type='image/png'),
        })
        self.assertIn('anh', response.context['form'].errors)

    def test_loi_nang_khi_may_o_cua_hang_thi_chuyen_bao_tri(self):
        don = self.tao_don()
        services.xac_nhan_lich(don.pk)
        may = PhanBoMay.objects.get(chi_tiet__don=don).may
        services.ghi_nhan_su_co(don.pk, self.nv, may, SuCo.NANG, 'Không lên nguồn', [tao_anh_png()])
        may.refresh_from_db()
        self.assertEqual(may.tinh_trang, May.BAO_TRI)

    def test_loi_nang_duoc_chon_san_khi_hoan_coc(self):
        don, may = self.don_dang_thue()
        services.ghi_nhan_su_co(don.pk, self.nv, may, SuCo.NANG, 'Vỡ ống kính', [tao_anh_png()])
        self.client.force_login(self.nv)
        response = self.client.get(reverse('ql_hoan_coc', args=[don.pk]))
        self.assertEqual(response.context['form'].initial['may_hu_hong'], [may.pk])

    def test_cap_nhat_da_xu_ly_can_ket_qua(self):
        don, may = self.don_dang_thue()
        su_co = services.ghi_nhan_su_co(don.pk, self.nv, may, SuCo.NHE, 'Trầy nhẹ viền máy', [tao_anh_png()])
        self.client.force_login(self.nv)
        url = reverse('ql_chi_tiet_su_co', args=[su_co.pk])

        self.client.post(url, {'trang_thai': SuCo.DA_XU_LY, 'ket_qua_xu_ly': ''})
        su_co.refresh_from_db()
        self.assertEqual(su_co.trang_thai, SuCo.CHO_XU_LY)

        self.client.post(url, {'trang_thai': SuCo.DA_XU_LY, 'ket_qua_xu_ly': 'Đã dán lại màn hình'})
        su_co.refresh_from_db()
        self.assertEqual(su_co.trang_thai, SuCo.DA_XU_LY)

    def test_khach_khong_vao_duoc_trang_su_co(self):
        self.client.force_login(self.khach)
        self.assertEqual(self.client.get(reverse('ql_su_co')).status_code, 403)


class BaoCaoTests(CoSoTest):
    """Trang báo cáo doanh thu có dữ liệu biểu đồ."""

    def test_du_lieu_bieu_do_theo_ngay_va_theo_may(self):
        don = self.tao_don()
        self.giao_may(don)
        self.client.force_login(self.chu)
        response = self.client.get(reverse('ql_bao_cao'))

        bieu_do = response.context['bieu_do']
        self.assertFalse(bieu_do['theo_thang'])
        self.assertEqual(sum(bieu_do['doanh_thu']), 120_000)
        self.assertEqual(bieu_do['ten_may'], ['Canon M50'])
        self.assertContains(response, 'id="du-lieu-bieu-do"')

    def test_khoang_dai_thi_gom_theo_thang(self):
        self.client.force_login(self.chu)
        response = self.client.get(reverse('ql_bao_cao'), {'tu': '2026-01-01', 'den': '2026-12-31'})
        self.assertTrue(response.context['bieu_do']['theo_thang'])
        self.assertEqual(len(response.context['bieu_do']['moc_thoi_gian']), 12)

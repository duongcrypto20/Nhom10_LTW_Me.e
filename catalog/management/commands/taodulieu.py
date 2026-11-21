"""
Lệnh tạo dữ liệu mẫu:   python manage.py taodulieu

Dữ liệu được tạo:
    - 6 tài khoản demo (1 chủ cửa hàng, 1 nhân viên, 4 khách hàng), mật khẩu chung 123456
    - 4 gói thuê cố định + 1 gói tùy chỉnh thời gian
    - 12 dòng máy, mỗi dòng 1-2 máy (số sê-ri), bảng giá và tiền cọc
    - 2 mã giảm giá
    - 9 đơn thuê mẫu ở đủ các trạng thái, kèm giao dịch tiền cọc
    - 3 đánh giá của khách và một số thông báo

Giá thuê lấy theo ảnh "THÔNG TIN/giá máy.jpg"; tiền cọc theo "quy định cọc.jpg"
(700.000đ mỗi máy, máy compact 300.000đ). Ảnh máy nằm trong media/thietbi/.

Chạy lại lệnh nhiều lần vẫn an toàn: tài khoản, máy, giá được cập nhật;
đơn thuê mẫu chỉ được tạo khi database chưa có đơn nào.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from catalog.models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi
from feedback.models import DanhGia
from rentals.models import ChiTietDonThue, DonThue, GiaoDich, PhanBoMay, ThongBao

MAT_KHAU_DEMO = '123456'

# ===========================================================================
# BẢNG DỮ LIỆU MẪU
# ===========================================================================

TAI_KHOAN = [
    # (email, họ tên, vai trò, số điện thoại, CCCD)
    ('chu@demo.com', 'Lê Quốc Bảo', User.CHU_CUA_HANG, '0905000001', ''),
    ('nv@demo.com', 'Trần Thu Hà', User.NHAN_VIEN, '0905000002', ''),
    ('khach@demo.com', 'Nguyễn Minh Anh', User.KHACH_HANG, '0905000003', '048203001234'),
    ('ngoc@demo.com', 'Trần Bảo Ngọc', User.KHACH_HANG, '0905000004', '048203005678'),
    ('phuc@demo.com', 'Lê Hoàng Phúc', User.KHACH_HANG, '0905000005', '048203009012'),
    ('trang@demo.com', 'Phạm Thu Trang', User.KHACH_HANG, '0905000006', '048203003456'),
]

GOI_THUE = [
    # (tên, số giờ tối đa, mô tả, gói tùy chỉnh?) - theo quy định "Giờ nhận - trả máy"
    ('6 giờ', 6, 'Thuê 1 buổi: ca sáng 8h-14h hoặc ca chiều tối 15h-21h', False),
    ('1 ngày', 23, 'Tính 23 giờ, ví dụ nhận 10h sáng nay trả 9h sáng mai', False),
    ('2 ngày', 47, 'Một chuyến đi ngắn', False),
    ('3 ngày', 71, 'Thêm thời gian trải nghiệm', False),
    ('Tùy chỉnh thời gian', 720, 'Tự chọn giờ nhận và trả, hệ thống ghép các gói rẻ nhất', True),
]

COC_THUONG = 700_000
COC_COMPACT = 300_000

THIET_BI = [
    # (mã, tên, hãng, loại, thông số, mô tả, ảnh, số máy,
    #  giá 6 giờ / 1 ngày / 2 ngày / 3 ngày tính theo nghìn đồng)
    ('m10', 'Canon EOS M10', 'Canon', 'mirrorless', 'APS-C · 18MP · Full HD',
     'Thân máy trắng nhỏ gọn, màn hình lật selfie.', 'canon-m10.jpg', 2, [90, 130, 250, 370]),
    ('m50', 'Canon EOS M50', 'Canon', 'mirrorless', 'APS-C · 24MP · 4K',
     'Thân máy nhỏ gọn, màu da đẹp, quay 4K.', 'canon-m50.jpg', 2, [120, 160, 310, 460]),
    ('r50', 'Canon EOS R50', 'Canon', 'mirrorless', 'APS-C · 24MP · 4K',
     'Thân máy nhỏ gọn, lấy nét nhanh, 4K.', 'canon-r50.jpg', 2, [180, 220, 430, 640]),
    ('xa3', 'Fujifilm X-A3', 'Fujifilm', 'mirrorless_co_dien', 'APS-C · 24MP · Full HD',
     'Ngoại hình cổ điển, màn hình lật selfie.', 'fuji-xa3.jpg', 2, [110, 150, 290, 430]),
    ('xt100', 'Fujifilm X-T100', 'Fujifilm', 'mirrorless_co_dien', 'APS-C · 24MP · 4K',
     'Ngoại hình cổ điển đẹp, màu film Fuji.', 'fuji-xt100.jpg', 2, [150, 190, 370, 550]),
    ('xt10', 'Fujifilm X-T10', 'Fujifilm', 'mirrorless_co_dien', 'APS-C · 16MP · Full HD',
     'Ngoại hình cổ điển, nhỏ nhẹ.', 'fuji-xt10.jpg', 1, [140, 180, 350, 520]),
    ('xt20', 'Fujifilm X-T20', 'Fujifilm', 'mirrorless_co_dien', 'APS-C · 24MP · 4K',
     'Ngoại hình đẹp, màu film Fuji, 4K.', 'fuji-xt20.jpg', 2, [180, 220, 430, 640]),
    ('xt30', 'Fujifilm X-T30', 'Fujifilm', 'mirrorless_co_dien', 'APS-C · 26MP · 4K',
     'Ngoại hình đẹp, lấy nét nhanh, 4K.', 'fuji-xt30.jpg', 2, [200, 270, 530, 790]),
    ('xs10', 'Fujifilm X-S10', 'Fujifilm', 'mirrorless', 'APS-C · 26MP · 4K · chống rung thân máy',
     'Báng cầm chắc tay, chống rung trong thân máy.', 'fuji-xs10.jpg', 1, [260, 320, 630, 940]),
    ('xs20', 'Fujifilm X-S20', 'Fujifilm', 'mirrorless', 'APS-C · 26MP · 6.2K · pin lớn',
     'Pin lâu, quay video đẹp, hợp làm vlog.', 'fuji-xs20.jpg', 1, [350, 400, 790, 1180]),
    ('x100v', 'Fujifilm X100V', 'Fujifilm', 'compact', 'APS-C · 26MP · ống kính 23mm f/2',
     'Máy nhỏ gọn, bỏ túi áo khoác đi cả ngày.', 'fuji-x100v.jpg', 2, [320, 390, 770, 1150]),
    ('xm5', 'Fujifilm X-M5', 'Fujifilm', 'mirrorless', 'APS-C · 26MP · 6.2K · nhẹ 355g',
     'Thân máy nhỏ nhất dòng X, có nút chọn giả lập màu film.', 'fuji-xm5.jpg', 1, [250, 300, 590, 880]),
]

MA_GIAM_GIA = [
    # (mã, loại, giá trị, số lượt)
    ('MEE10', MaGiamGia.PHAN_TRAM, 10, 20),
    ('GIAM50K', MaGiamGia.SO_TIEN, 50_000, 10),
]


class Command(BaseCommand):
    help = 'Tạo hoặc cập nhật dữ liệu mẫu cho website me.e_digitalcam'

    # -----------------------------------------------------------------------
    # Hàm chính
    # -----------------------------------------------------------------------

    @transaction.atomic
    def handle(self, *args, **options):
        self.tao_tai_khoan()
        self.tao_goi_thue()
        self.tao_thiet_bi()
        self.tao_ma_giam_gia()

        if DonThue.objects.exists():
            self.stdout.write('Database đã có đơn thuê, bỏ qua bước tạo đơn mẫu.')
        else:
            self.tao_don_mau()

        self.stdout.write(self.style.SUCCESS('Đã tạo / cập nhật dữ liệu mẫu.'))
        self.stdout.write(f'Tài khoản demo (mật khẩu {MAT_KHAU_DEMO}): '
                          + ', '.join(email for email, *_ in TAI_KHOAN))

    # -----------------------------------------------------------------------
    # 1. Tài khoản
    # -----------------------------------------------------------------------

    def tao_tai_khoan(self):
        for email, ho_ten, vai_tro, so_dien_thoai, cccd in TAI_KHOAN:
            if User.objects.filter(username=email).exists():
                continue
            la_chu = vai_tro == User.CHU_CUA_HANG
            User.objects.create_user(
                username=email,
                email=email,
                password=MAT_KHAU_DEMO,
                ho_ten=ho_ten,
                vai_tro=vai_tro,
                so_dien_thoai=so_dien_thoai,
                cccd=cccd,
                is_staff=la_chu,       # chủ cửa hàng vào được trang /admin/
                is_superuser=la_chu,
            )

    # -----------------------------------------------------------------------
    # 2. Gói thuê
    # -----------------------------------------------------------------------

    def tao_goi_thue(self):
        for ten, so_gio, mo_ta, tuy_chinh in GOI_THUE:
            GoiThue.objects.update_or_create(
                ten=ten,
                defaults={'so_gio_toi_da': so_gio, 'mo_ta': mo_ta, 'tuy_chinh': tuy_chinh},
            )

    # -----------------------------------------------------------------------
    # 3. Thiết bị, máy vật lý và bảng giá
    # -----------------------------------------------------------------------

    def tao_thiet_bi(self):
        ds_goi_co_gia = list(GoiThue.objects.filter(tuy_chinh=False).order_by('so_gio_toi_da'))

        for ma, ten, hang, loai, thong_so, mo_ta, anh, so_may, ds_gia in THIET_BI:
            danh_muc, _ = LoaiThietBi.objects.get_or_create(
                ma=loai, defaults={'ten': dict(ThietBi.LOAI)[loai]},
            )
            thiet_bi, _ = ThietBi.objects.get_or_create(ma=ma, defaults={
                'ten': ten,
                'hang': hang,
                'loai': loai,
                'danh_muc': danh_muc,
                'thong_so': thong_so,
                'mo_ta': mo_ta,
                'phu_hop': 'Du lịch, chụp đời thường, chụp kỷ yếu',
            })

            # Ảnh và tiền cọc luôn cập nhật theo quy định cọc
            thiet_bi.anh = 'thietbi/' + anh
            thiet_bi.tien_coc = COC_COMPACT if loai == 'compact' else COC_THUONG
            thiet_bi.gia_tri_den_bu = thiet_bi.tien_coc * 10
            thiet_bi.save()

            # Máy vật lý: SN-R50-01, SN-R50-02...
            for so_thu_tu in range(1, so_may + 1):
                May.objects.get_or_create(
                    so_seri=f'SN-{ma.upper()}-{so_thu_tu:02d}',
                    defaults={'thiet_bi': thiet_bi},
                )

            # Bảng giá theo 4 gói cố định
            for goi, gia_nghin in zip(ds_goi_co_gia, ds_gia):
                GiaThue.objects.update_or_create(
                    thiet_bi=thiet_bi, goi_thue=goi, defaults={'gia': gia_nghin * 1000},
                )

    # -----------------------------------------------------------------------
    # 4. Mã giảm giá
    # -----------------------------------------------------------------------

    def tao_ma_giam_gia(self):
        for ma, loai, gia_tri, so_luot in MA_GIAM_GIA:
            MaGiamGia.objects.get_or_create(
                ma=ma, defaults={'loai': loai, 'gia_tri': gia_tri, 'so_luot': so_luot},
            )

    # -----------------------------------------------------------------------
    # 5. Đơn thuê mẫu ở đủ các trạng thái
    # -----------------------------------------------------------------------

    def tao_don(self, email, ma_may, ten_goi, ngay_lech, trang_thai, so_luong=1, **thong_tin_them):
        """
        Tạo một đơn mẫu cùng chi tiết đơn và máy được giữ.

        ngay_lech: số ngày so với hôm nay (âm là quá khứ). Giờ nhận luôn là 9h sáng.
        """
        khach = User.objects.get(username=email)
        thiet_bi = ThietBi.objects.get(ma=ma_may)
        goi = GoiThue.objects.get(ten=ten_goi)
        gia = GiaThue.objects.get(thiet_bi=thiet_bi, goi_thue=goi).gia

        hom_nay_9h = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        gio_nhan = hom_nay_9h + timedelta(days=ngay_lech)
        gio_tra = gio_nhan + timedelta(hours=goi.so_gio_toi_da)

        don = DonThue.objects.create(
            khach_hang=khach,
            thiet_bi=thiet_bi,
            goi_thue=goi,
            gio_nhan=gio_nhan,
            gio_tra=gio_tra,
            tien_thue=gia * so_luong,
            tien_coc=thiet_bi.tien_coc * so_luong,
            trang_thai=trang_thai,
            **thong_tin_them,
        )
        chi_tiet = ChiTietDonThue.objects.create(
            don=don,
            thiet_bi=thiet_bi,
            so_luong=so_luong,
            don_gia=gia,
            tien_coc_don_vi=thiet_bi.tien_coc,
            cach_tinh_gia=f'{goi.ten}, số lượng 1: {gia:,}đ'.replace(',', '.'),
        )

        # Đơn đã xác nhận trở đi thì đã có máy được giữ
        if trang_thai in (DonThue.DA_XAC_NHAN, DonThue.DANG_THUE, DonThue.HOAN_TAT):
            for may in thiet_bi.cac_may.all()[:so_luong]:
                PhanBoMay.objects.create(chi_tiet=chi_tiet, may=may)
        return don

    def ghi_tien(self, don, loai, so_tien, phuong_thuc='tien_mat'):
        """Ghi một giao dịch mẫu, người ghi là nhân viên demo (trừ cọc online)."""
        nhan_vien = None if phuong_thuc == 'online' else User.objects.get(username='nv@demo.com')
        GiaoDich.objects.create(
            don=don, loai=loai, so_tien=so_tien, phuong_thuc=phuong_thuc, nguoi_xac_nhan=nhan_vien,
        )

    def hoan_tat_don(self, don, tre_gio=0, khau_tru=0, mo_ta=''):
        """Đưa đơn mẫu về trạng thái đã trả máy, đã hoàn cọc."""
        # Khách cọc lịch online, phần còn lại và tiền thuê thu khi nhận máy
        self.ghi_tien(don, GiaoDich.DAT_COC, DonThue.COC_GIU_LICH, 'online')
        self.ghi_tien(don, GiaoDich.DAT_COC, don.tien_coc - DonThue.COC_GIU_LICH)
        self.ghi_tien(don, GiaoDich.THANH_TOAN, don.tong_thanh_toan)

        # Trả máy, tính phụ thu và hoàn cọc
        don.giao_thuc_te = don.gio_nhan
        don.tra_thuc_te = don.gio_tra + timedelta(hours=tre_gio)
        don.hinh_thuc_tra = 'truc_tiep'
        don.phu_thu_tra_tre = 50_000 * tre_gio
        don.khau_tru_den_bu = khau_tru
        don.hoan_lai = max(don.tien_coc - don.phu_thu_tra_tre - khau_tru, 0)
        don.trang_thai_coc = DonThue.DA_HOAN if don.hoan_lai == don.tien_coc else DonThue.HOAN_MOT_PHAN
        don.hinh_thuc_coc = 'online'
        don.tinh_trang_khi_tra = mo_ta or 'Máy bình thường'
        don.save()
        self.ghi_tien(don, GiaoDich.HOAN_COC, don.hoan_lai)

    def tao_don_mau(self):
        # --- Ba đơn đã hoàn tất (để có báo cáo doanh thu và đánh giá) ---
        don_1 = self.tao_don('khach@demo.com', 'r50', '1 ngày', -14, DonThue.HOAN_TAT)
        self.hoan_tat_don(don_1)

        don_2 = self.tao_don('ngoc@demo.com', 'xt30', '2 ngày', -10, DonThue.HOAN_TAT)
        self.hoan_tat_don(don_2, tre_gio=2)

        don_3 = self.tao_don('phuc@demo.com', 'm50', '1 ngày', -7, DonThue.HOAN_TAT)
        self.hoan_tat_don(don_3, khau_tru=200_000, mo_ta='SN-M50-01: trầy nhẹ màn hình')

        # --- Đơn đang thuê: nhận hôm qua, trả trong 2 ngày tới ---
        don_4 = self.tao_don('khach@demo.com', 'x100v', '3 ngày', -1, DonThue.DANG_THUE,
                             trang_thai_coc=DonThue.DA_THU, hinh_thuc_coc='online')
        self.ghi_tien(don_4, GiaoDich.DAT_COC, DonThue.COC_GIU_LICH, 'online')
        self.ghi_tien(don_4, GiaoDich.DAT_COC, don_4.tien_coc - DonThue.COC_GIU_LICH)
        self.ghi_tien(don_4, GiaoDich.THANH_TOAN, don_4.tong_thanh_toan)
        don_4.giao_thuc_te = don_4.gio_nhan
        don_4.save()
        May.objects.filter(cac_phan_bo__chi_tiet__don=don_4).update(tinh_trang=May.DANG_THUE)

        # --- Đơn đã cọc lịch online, chờ khách đến nhận máy ---
        don_5 = self.tao_don('ngoc@demo.com', 'xs20', '1 ngày', 2, DonThue.DA_XAC_NHAN,
                             trang_thai_coc=DonThue.DA_THU, hinh_thuc_coc='online')
        self.ghi_tien(don_5, GiaoDich.DAT_COC, DonThue.COC_GIU_LICH, 'online')

        # --- Đơn nhân viên đã giữ máy nhưng khách chưa cọc ---
        self.tao_don('trang@demo.com', 'xa3', '2 ngày', 3, DonThue.DA_XAC_NHAN)

        # --- Đơn mới đặt, đang chờ xử lý (2 máy, có mã giảm giá) ---
        don_7 = self.tao_don('phuc@demo.com', 'm10', '6 giờ', 5, DonThue.CHO_XU_LY, so_luong=2,
                             ma_giam_gia='MEE10')
        don_7.giam_gia = don_7.tien_thue // 10
        don_7.save()

        # --- Đơn cần khách điều chỉnh và đơn đã hủy ---
        self.tao_don('trang@demo.com', 'xt20', '3 ngày', 6, DonThue.CAN_DIEU_CHINH,
                     ly_do='Ngày này X-T20 đã kín lịch, bạn có thể chọn X-T30 hoặc lùi 1 ngày.')
        self.tao_don('khach@demo.com', 'r50', '1 ngày', 4, DonThue.DA_HUY,
                     ly_do='Khách hàng hủy yêu cầu.')

        self.tao_danh_gia_va_thong_bao(don_1, don_2, don_3, don_5)
        self.stdout.write('Đã tạo 9 đơn thuê mẫu, 3 đánh giá và thông báo.')

    # -----------------------------------------------------------------------
    # 6. Đánh giá và thông báo mẫu
    # -----------------------------------------------------------------------

    def tao_danh_gia_va_thong_bao(self, don_1, don_2, don_3, don_5):
        DanhGia.objects.create(
            don=don_1, so_sao=5, trang_thai=DanhGia.DA_DUYET,
            noi_dung='Máy đẹp, pin trâu, nhân viên hướng dẫn kỹ. Sẽ thuê lại!',
        )
        DanhGia.objects.create(
            don=don_2, so_sao=4, trang_thai=DanhGia.DA_DUYET,
            noi_dung='Màu film Fuji rất thích, mình trả trễ 2 tiếng nên bị phụ thu.',
            tra_loi='Cảm ơn bạn đã thuê máy. Lần sau bạn nhắn trước để shop gia hạn nhé!',
        )
        DanhGia.objects.create(
            don=don_3, so_sao=3, trang_thai=DanhGia.CHO_XU_LY,
            noi_dung='Máy dùng ổn nhưng mình lỡ làm trầy màn hình.',
        )

        nhan_vien = User.objects.get(username='nv@demo.com')
        ThongBao.objects.create(
            nguoi_nhan=don_5.khach_hang, don=don_5, tieu_de='Đặt cọc thành công',
            noi_dung=f'{don_5.ma}: cọc lịch thành công 50.000đ. Đã giữ máy cho bạn.',
        )
        ThongBao.objects.create(
            nguoi_nhan=nhan_vien, don=don_5, tieu_de='Khách đã đặt cọc',
            noi_dung=f'{don_5.ma}: khách đã cọc lịch 50.000đ, hệ thống đã giữ máy.',
        )
        ThongBao.objects.create(
            nguoi_nhan=nhan_vien, don=don_3, tieu_de='Phản hồi mới',
            noi_dung=f'{don_3.ma}: khách vừa gửi đánh giá 3 sao.',
        )

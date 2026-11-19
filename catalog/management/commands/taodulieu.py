"""
Lệnh tạo dữ liệu mẫu:  python manage.py taodulieu

Tạo 3 tài khoản demo, 4 gói thuê, 12 dòng máy, bảng giá và 1 mã giảm giá.
Giá thuê lấy đúng theo ảnh "THÔNG TIN/giá máy.jpg"; tiền cọc theo "quy định cọc.jpg"
(700.000đ mỗi máy, máy compact 300.000đ). Ảnh máy lấy từ thư mục "ẢNH MÁY ẢNH".

Chạy lại lệnh này nhiều lần vẫn an toàn: giá, tiền cọc và ảnh được cập nhật theo bảng bên dưới.
"""
from django.core.management.base import BaseCommand

from accounts.models import User
from catalog.models import GiaThue, GoiThue, LoaiThietBi, MaGiamGia, May, ThietBi

TAI_KHOAN = [
    # (email, họ tên, vai trò)
    ('chu@demo.vn', 'Lê Quốc Bảo', User.CHU_CUA_HANG),
    ('nv@demo.vn', 'Trần Thu Hà', User.NHAN_VIEN),
    ('khach@demo.vn', 'Nguyễn Minh Anh', User.KHACH_HANG),
]

GOI_THUE = [
    # (tên, số giờ tối đa, mô tả) - theo quy định "Giờ nhận - trả máy"
    ('6 giờ', 6, 'Thuê 1 buổi: ca sáng 8h-14h hoặc ca chiều tối 15h-21h'),
    ('1 ngày', 23, 'Tính 23 giờ, ví dụ nhận 10h sáng nay trả 9h sáng mai'),
    ('2 ngày', 47, 'Một chuyến đi ngắn'),
    ('3 ngày', 71, 'Thêm thời gian trải nghiệm'),
]

COC_THUONG, COC_COMPACT = 700000, 300000

THIET_BI = [
    # (mã, tên, hãng, loại, thông số, mô tả, ảnh, số máy, giá 6H / 1 ngày / 2 ngày / 3 ngày tính theo nghìn đồng)
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


class Command(BaseCommand):
    help = 'Tạo hoặc cập nhật dữ liệu mẫu cho website me.e_digitalcam'

    def handle(self, *args, **options):
        # 1. Tài khoản demo, mật khẩu chung là 123456
        for email, ho_ten, vai_tro in TAI_KHOAN:
            if not User.objects.filter(username=email).exists():
                user = User.objects.create_user(username=email, email=email, password='123456',
                                                ho_ten=ho_ten, vai_tro=vai_tro)
                if vai_tro == User.CHU_CUA_HANG:
                    # Cho chủ cửa hàng vào được trang /admin/
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()

        # 2. Gói thuê
        ds_goi = []
        for ten, so_gio, mo_ta in GOI_THUE:
            goi, _ = GoiThue.objects.update_or_create(ten=ten, defaults={'so_gio_toi_da': so_gio, 'mo_ta': mo_ta})
            ds_goi.append(goi)

        # 3. Thiết bị, máy vật lý và bảng giá
        for ma, ten, hang, loai, thong_so, mo_ta, anh, so_may, ds_gia in THIET_BI:
            danh_muc, _ = LoaiThietBi.objects.get_or_create(ma=loai, defaults={'ten': dict(ThietBi.LOAI).get(loai, loai)})
            thiet_bi, da_tao = ThietBi.objects.get_or_create(ma=ma, defaults={
                'ten': ten, 'hang': hang, 'loai': loai, 'danh_muc': danh_muc, 'thong_so': thong_so, 'mo_ta': mo_ta,
                'phu_hop': 'Du lịch, chụp đời thường, chụp kỷ yếu',
            })
            # Luôn cập nhật ảnh và tiền cọc theo thư mục ảnh và quy định cọc
            thiet_bi.anh = 'thietbi/' + anh
            thiet_bi.tien_coc = COC_COMPACT if loai == 'compact' else COC_THUONG
            thiet_bi.save(update_fields=['anh', 'tien_coc'])
            for i in range(1, so_may + 1):
                May.objects.get_or_create(so_seri=f'SN-{ma.upper()}-0{i}', defaults={'thiet_bi': thiet_bi})
            for goi, gia_nghin in zip(ds_goi, ds_gia):
                GiaThue.objects.update_or_create(thiet_bi=thiet_bi, goi_thue=goi, defaults={'gia': gia_nghin * 1000})

        # 4. Mã giảm giá
        MaGiamGia.objects.get_or_create(ma='MEE10', defaults={
            'loai': MaGiamGia.PHAN_TRAM, 'gia_tri': 10, 'so_luot': 20})

        self.stdout.write(self.style.SUCCESS(f'Đã tạo / cập nhật {len(THIET_BI)} dòng máy và bảng giá.'))
        self.stdout.write('Tài khoản demo (mật khẩu 123456): chu@demo.vn, nv@demo.vn, khach@demo.vn')

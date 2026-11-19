from django.conf import settings
from django.db import models

from catalog.models import GoiThue, May, ThietBi


class DonThue(models.Model):
    """Đơn thuê nhiều thiết bị theo một gói và khoảng thời gian chung (UC-1, UC-5)."""

    COC_GIU_LICH = 50_000

    # Trạng thái đơn
    CHO_XU_LY = 'cho_xu_ly'
    CAN_DIEU_CHINH = 'can_dieu_chinh'
    DA_XAC_NHAN = 'da_xac_nhan'
    DANG_THUE = 'dang_thue'
    HOAN_TAT = 'hoan_tat'
    DA_HUY = 'da_huy'
    TRANG_THAI = [
        (CHO_XU_LY, 'Chờ xử lý'),
        (CAN_DIEU_CHINH, 'Cần điều chỉnh'),
        (DA_XAC_NHAN, 'Đã xác nhận'),
        (DANG_THUE, 'Đang thuê'),
        (HOAN_TAT, 'Đã hoàn tất'),
        (DA_HUY, 'Đã hủy'),
    ]

    # Trạng thái tiền cọc
    CHUA_THU = 'chua_thu'
    DA_THU = 'da_thu'
    DA_HOAN = 'da_hoan'
    HOAN_MOT_PHAN = 'hoan_mot_phan'
    KHAU_TRU_TOAN_BO = 'khau_tru_toan_bo'
    TRANG_THAI_COC = [
        (CHUA_THU, 'Chưa thu'),
        (DA_THU, 'Đã thu'),
        (DA_HOAN, 'Đã hoàn'),
        (HOAN_MOT_PHAN, 'Hoàn một phần'),
        (KHAU_TRU_TOAN_BO, 'Đã khấu trừ toàn bộ'),
    ]

    HINH_THUC_TRA = [
        ('truc_tiep', 'Trả trực tiếp tại cửa hàng'),
        ('gui_ve', 'Gửi máy về cửa hàng'),
    ]
    # Cách thu tiền: khách cọc online trên website, hoặc nhân viên thu tại cửa hàng
    HINH_THUC_COC = [
        ('online', 'Cọc online'),
        ('chuyen_khoan', 'Chuyển khoản'),
        ('tien_mat', 'Tiền mặt'),
    ]
    HINH_THUC_THU_TAI_QUAY = [
        ('tien_mat', 'Tiền mặt'),
        ('chuyen_khoan', 'Chuyển khoản'),
    ]

    # Thông tin yêu cầu thuê (khách nhập)
    khach_hang = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='cac_don')
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.PROTECT, related_name='cac_don')
    goi_thue = models.ForeignKey(GoiThue, on_delete=models.PROTECT)
    gio_nhan = models.DateTimeField('Giờ nhận máy')
    gio_tra = models.DateTimeField('Giờ trả dự kiến')
    ghi_chu = models.TextField(blank=True)

    # Tiền
    tien_thue = models.PositiveIntegerField(default=0)
    giam_gia = models.PositiveIntegerField(default=0)
    ma_giam_gia = models.CharField(max_length=20, blank=True)
    tien_coc = models.PositiveIntegerField(default=0)

    # Xử lý của cửa hàng
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default=CHO_XU_LY)
    ly_do = models.TextField('Lý do điều chỉnh hoặc hủy', blank=True)
    may = models.ForeignKey(May, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='cac_don')

    # Tiền cọc
    trang_thai_coc = models.CharField(max_length=20, choices=TRANG_THAI_COC, default=CHUA_THU)
    hinh_thuc_coc = models.CharField(max_length=20, choices=HINH_THUC_COC, blank=True)
    phu_thu_tra_tre = models.PositiveIntegerField(default=0)
    khau_tru_den_bu = models.PositiveIntegerField(default=0)
    hoan_lai = models.PositiveIntegerField(default=0)

    # Giao máy và nhận trả
    giao_thuc_te = models.DateTimeField(null=True, blank=True)
    tra_thuc_te = models.DateTimeField(null=True, blank=True)
    hinh_thuc_tra = models.CharField(max_length=20, choices=HINH_THUC_TRA, blank=True)
    tinh_trang_khi_giao = models.TextField(blank=True)
    tinh_trang_khi_tra = models.TextField(blank=True)
    ma_van_don_tra = models.CharField('Mã vận đơn trả máy', max_length=100, blank=True)
    don_vi_van_chuyen = models.CharField('Đơn vị vận chuyển', max_length=100, blank=True)
    ngay_bao_tra = models.DateTimeField(null=True, blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)
    ma_gui = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['-ngay_tao']

    def __str__(self):
        return self.ma

    @property
    def ma(self):
        """Mã đơn hiển thị cho người dùng, ví dụ DH1001."""
        return f'DH{1000 + self.pk}'

    @property
    def tong_thanh_toan(self):
        return self.tien_thue - self.giam_gia

    @property
    def tien_coc_giu_lich(self):
        """Cọc lịch tính vào cọc máy, không thu vượt tổng cọc của đơn."""
        return min(self.COC_GIU_LICH, self.tien_coc)

    @property
    def tien_coc_da_thu(self):
        if not self.pk:
            return 0
        return sum(gd.so_tien for gd in self.cac_giao_dich.all()
                   if gd.loai == 'dat_coc' and gd.trang_thai == 'thanh_cong')

    @property
    def tien_coc_con_lai(self):
        return max(self.tien_coc - self.tien_coc_da_thu, 0)

    @property
    def buoc_hien_tai(self):
        """Số mốc đã đạt: Đã đặt đơn, Đã giữ máy, Đã cọc, Đang thuê, Hoàn tất."""
        if self.trang_thai == self.DA_XAC_NHAN and self.trang_thai_coc != self.CHUA_THU:
            return 3
        thu_tu = {
            self.CHO_XU_LY: 1, self.CAN_DIEU_CHINH: 1, self.DA_HUY: 1,
            self.DA_XAC_NHAN: 2, self.DANG_THUE: 4, self.HOAN_TAT: 5,
        }
        return thu_tu[self.trang_thai]

    @property
    def cho_dat_coc(self):
        """Đơn mới đặt (hoặc đã được nhân viên xác nhận) mà khách chưa cọc: khách cọc online để giữ máy."""
        return self.trang_thai in (self.CHO_XU_LY, self.DA_XAC_NHAN) and self.trang_thai_coc == self.CHUA_THU

    @property
    def co_the_huy(self):
        # Quy định cửa hàng: đã cọc thì không nhận hủy lịch
        return self.trang_thai in (self.CHO_XU_LY, self.CAN_DIEU_CHINH) or self.cho_dat_coc

    @property
    def ten_thiet_bi(self):
        dong = list(self.cac_chi_tiet.all())
        return ', '.join(f'{d.thiet_bi.ten} × {d.so_luong}' for d in dong) or self.thiet_bi.ten

    @property
    def can_thu_them(self):
        return max(self.phu_thu_tra_tre + self.khau_tru_den_bu - self.tien_coc, 0)


class ChiTietDonThue(models.Model):
    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_chi_tiet')
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.PROTECT)
    so_luong = models.PositiveIntegerField('Số lượng', default=1)
    don_gia = models.PositiveIntegerField('Đơn giá tại thời điểm đặt thuê')
    tien_coc_don_vi = models.PositiveIntegerField(default=0)
    cach_tinh_gia = models.TextField('Cách tính giá đã chốt', blank=True)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['don', 'thiet_bi'], name='mot_dong_moi_thiet_bi'),
            models.CheckConstraint(condition=models.Q(so_luong__gt=0), name='so_luong_thue_duong')]

    @property
    def thanh_tien(self):
        return self.so_luong * self.don_gia


class PhanBoMay(models.Model):
    chi_tiet = models.ForeignKey(ChiTietDonThue, on_delete=models.CASCADE, related_name='cac_phan_bo')
    may = models.ForeignKey(May, on_delete=models.PROTECT, related_name='cac_phan_bo')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chi_tiet', 'may'], name='may_trong_dong_duy_nhat')]


class KiemTraThietBi(models.Model):
    LOAI = [('giao', 'Trước khi giao'), ('tra', 'Khi nhận trả')]
    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_kiem_tra')
    may = models.ForeignKey(May, on_delete=models.PROTECT)
    nhan_vien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    loai = models.CharField(max_length=10, choices=LOAI)
    ben_ngoai = models.TextField('Tình trạng bên ngoài')
    hoat_dong = models.TextField('Hoạt động của máy')
    thau_kinh = models.TextField('Tình trạng thấu kính', blank=True)
    phu_kien = models.TextField('Phụ kiện đi kèm', blank=True)
    co_hu_hong = models.BooleanField(default=False)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ngay_tao']
        constraints = [models.UniqueConstraint(fields=['don', 'may', 'loai'], name='kiem_tra_moi_lan_ban_giao')]


class GiaoDich(models.Model):
    """Một lần thu hoặc chi tiền gắn với đơn thuê."""

    LOAI = [
        ('dat_coc', 'Đặt cọc'),
        ('thanh_toan', 'Thanh toán tiền thuê'),
        ('hoan_coc', 'Hoàn cọc'),
        ('phu_thu', 'Thu bổ sung phụ thu / đền bù'),
    ]

    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_giao_dich')
    loai = models.CharField(max_length=20, choices=LOAI)
    so_tien = models.PositiveIntegerField()
    phuong_thuc = models.CharField(max_length=20, choices=DonThue.HINH_THUC_COC, default='tien_mat')
    trang_thai = models.CharField(max_length=20, choices=[('cho_duyet', 'Chờ đối chiếu'),
        ('thanh_cong', 'Thành công'), ('tu_choi', 'Từ chối')], default='thanh_cong')
    ma_tham_chieu = models.CharField('Mã tham chiếu ngân hàng', max_length=100, null=True, blank=True, unique=True)
    minh_chung = models.ImageField('Ảnh giao dịch', upload_to='giaodich/', blank=True)
    ghi_chu = models.TextField('Ghi chú đối chiếu', blank=True)
    nguoi_xac_nhan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cac_giao_dich_da_duyet')
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']


class SuCo(models.Model):
    """Sự cố của máy trong lúc thuê hoặc khi hoàn cọc (hỏng hóc, mất, thiếu phụ kiện)."""

    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_su_co')
    may = models.ForeignKey(May, on_delete=models.SET_NULL, null=True)
    mo_ta = models.TextField()
    chi_phi = models.PositiveIntegerField(default=0)
    loai = models.CharField('Loại sự cố', max_length=30, default='hu_hong', choices=[
        ('hu_hong', 'Hư hỏng'), ('mat_may', 'Mất máy'), ('thieu_phu_kien', 'Thiếu phụ kiện')])
    trang_thai = models.CharField('Trạng thái xử lý', max_length=20, default='cho_xu_ly', choices=[
        ('cho_xu_ly', 'Chờ xử lý'), ('dang_xu_ly', 'Đang xử lý'), ('da_xu_ly', 'Đã xử lý')])
    cach_xu_ly = models.TextField('Kết quả xử lý', blank=True)
    nhan_vien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']


class AnhSuCo(models.Model):
    """Ảnh chụp tình trạng máy hỏng, nhân viên tải lên khi ghi nhận sự cố."""

    su_co = models.ForeignKey(SuCo, on_delete=models.CASCADE, related_name='cac_anh')
    anh = models.ImageField('Ảnh tình trạng máy', upload_to='su_co/')
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ngay_tao']


class BaoTri(models.Model):
    """Lịch sử bảo trì của một máy."""

    may = models.ForeignKey(May, on_delete=models.CASCADE, related_name='cac_bao_tri')
    ngay = models.DateField('Ngày bảo trì')
    noi_dung = models.TextField('Nội dung bảo trì')
    chi_phi = models.PositiveIntegerField('Chi phí (đồng)', default=0)
    hoan_tat = models.BooleanField('Đã hoàn tất bảo trì', default=False)
    nhan_vien = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-ngay']


class ThongBao(models.Model):
    """Thông báo gửi cho người dùng khi đơn thuê thay đổi trạng thái."""

    nguoi_nhan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='cac_thong_bao')
    noi_dung = models.CharField(max_length=255)
    tieu_de = models.CharField(max_length=150, default='Thông báo từ me.e_digitalcam')
    don = models.ForeignKey(DonThue, on_delete=models.SET_NULL, null=True, blank=True)
    da_doc = models.BooleanField(default=False)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']

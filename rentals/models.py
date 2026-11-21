"""
Các bảng dữ liệu của app rentals (đặt thuê và tiền cọc).

    DonThue          : một đơn thuê của khách (UC-1)
    ChiTietDonThue   : từng dòng máy trong đơn, kèm số lượng và đơn giá đã chốt
    PhanBoMay        : chiếc máy (số sê-ri) được giữ cho từng dòng của đơn
    GiaoDich         : sổ ghi tiền: đặt cọc, thanh toán tiền thuê, hoàn cọc, thu thêm
    ThongBao         : thông báo gửi cho khách hàng và nhân viên
    SuCo, AnhSuCo    : sự cố của máy (mức độ, mô tả) và ảnh chụp chỗ hỏng
"""
from django.conf import settings
from django.db import models

from catalog.models import GoiThue, May, ThietBi


# ===========================================================================
# 1. ĐƠN THUÊ
# ===========================================================================

class DonThue(models.Model):
    """Một đơn thuê: khách chọn máy, gói thuê, giờ nhận và giờ trả."""

    # Tiền cọc lịch khách trả online để giữ máy (tính vào tổng cọc máy)
    COC_GIU_LICH = 50_000

    # ----- Trạng thái của đơn -----
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

    # ----- Trạng thái của tiền cọc -----
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

    # ----- Các lựa chọn khác -----
    HINH_THUC_TRA = [
        ('truc_tiep', 'Trả trực tiếp tại cửa hàng'),
        ('gui_ve', 'Gửi máy về cửa hàng'),
    ]
    PHUONG_THUC_TIEN = [
        ('online', 'Cọc online'),
        ('chuyen_khoan', 'Chuyển khoản'),
        ('tien_mat', 'Tiền mặt'),
    ]
    # Tại quầy chỉ thu tiền mặt hoặc chuyển khoản
    PHUONG_THUC_TAI_QUAY = [
        ('tien_mat', 'Tiền mặt'),
        ('chuyen_khoan', 'Chuyển khoản'),
    ]

    # ----- Thông tin khách nhập khi đặt thuê -----
    khach_hang = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cac_don',
    )
    # Dòng máy đầu tiên của đơn, dùng để hiển thị nhanh trong danh sách
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.PROTECT, related_name='cac_don')
    goi_thue = models.ForeignKey(GoiThue, on_delete=models.PROTECT)
    gio_nhan = models.DateTimeField('Giờ nhận máy')
    gio_tra = models.DateTimeField('Giờ trả dự kiến')
    ghi_chu = models.TextField('Ghi chú', blank=True)

    # ----- Tiền thuê -----
    tien_thue = models.PositiveIntegerField('Tiền thuê', default=0)
    giam_gia = models.PositiveIntegerField('Giảm giá', default=0)
    ma_giam_gia = models.CharField('Mã giảm giá', max_length=20, blank=True)

    # ----- Xử lý của cửa hàng -----
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default=CHO_XU_LY)
    ly_do = models.TextField('Lý do điều chỉnh hoặc hủy', blank=True)

    # ----- Tiền cọc (phần tiền cọc được gộp vào luồng đặt thuê) -----
    tien_coc = models.PositiveIntegerField('Tổng cọc máy', default=0)
    trang_thai_coc = models.CharField(max_length=20, choices=TRANG_THAI_COC, default=CHUA_THU)
    hinh_thuc_coc = models.CharField(max_length=20, choices=PHUONG_THUC_TIEN, blank=True)
    phu_thu_tra_tre = models.PositiveIntegerField('Phụ thu trả trễ', default=0)
    khau_tru_den_bu = models.PositiveIntegerField('Khấu trừ đền bù', default=0)
    hoan_lai = models.PositiveIntegerField('Tiền cọc hoàn lại', default=0)

    # ----- Thời điểm khách nhận máy và trả máy -----
    giao_thuc_te = models.DateTimeField('Giờ giao thực tế', null=True, blank=True)
    tra_thuc_te = models.DateTimeField('Giờ trả thực tế', null=True, blank=True)
    hinh_thuc_tra = models.CharField(max_length=20, choices=HINH_THUC_TRA, blank=True)
    tinh_trang_khi_tra = models.TextField('Tình trạng máy khi trả', blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)
    # Mã ngẫu nhiên của lần bấm gửi đơn, chống tạo trùng đơn khi khách bấm hai lần
    ma_gui = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['-ngay_tao']
        verbose_name = 'Đơn thuê'
        verbose_name_plural = 'Đơn thuê'

    def __str__(self):
        return self.ma

    # ----- Các giá trị tính sẵn để dùng trong template -----

    @property
    def ma(self):
        """Mã đơn hiển thị cho người dùng, ví dụ DH1001."""
        return f'DH{1000 + self.pk}'

    @property
    def tong_thanh_toan(self):
        """Tiền thuê sau khi trừ giảm giá."""
        return self.tien_thue - self.giam_gia

    @property
    def tien_coc_giu_lich(self):
        """Cọc lịch 50.000đ, nhưng không vượt quá tổng cọc của đơn."""
        return min(self.COC_GIU_LICH, self.tien_coc)

    @property
    def tien_coc_da_thu(self):
        """Tổng tiền cọc đã thu (cọc lịch online và phần thu tại quầy)."""
        if not self.pk:
            return 0
        return sum(gd.so_tien for gd in self.cac_giao_dich.all() if gd.loai == GiaoDich.DAT_COC)

    @property
    def tien_coc_con_lai(self):
        """Phần cọc máy còn phải thu khi khách đến nhận máy."""
        return max(self.tien_coc - self.tien_coc_da_thu, 0)

    @property
    def can_thu_them(self):
        """Phụ thu và đền bù vượt quá tiền cọc thì phải thu thêm của khách."""
        return max(self.phu_thu_tra_tre + self.khau_tru_den_bu - self.tien_coc, 0)

    @property
    def cho_dat_coc(self):
        """Đơn mới đặt hoặc đã được giữ máy nhưng khách chưa cọc."""
        return (
            self.trang_thai in (self.CHO_XU_LY, self.DA_XAC_NHAN)
            and self.trang_thai_coc == self.CHUA_THU
        )

    @property
    def co_the_huy(self):
        """Quy định cửa hàng: đơn đã cọc thì không nhận hủy lịch."""
        return self.trang_thai in (self.CHO_XU_LY, self.CAN_DIEU_CHINH) or self.cho_dat_coc

    @property
    def buoc_hien_tai(self):
        """Mốc trên thanh tiến trình: 1 Đặt đơn, 2 Giữ máy, 3 Đã cọc, 4 Đang thuê, 5 Hoàn tất."""
        if self.trang_thai == self.DA_XAC_NHAN and self.trang_thai_coc != self.CHUA_THU:
            return 3
        thu_tu = {
            self.CHO_XU_LY: 1,
            self.CAN_DIEU_CHINH: 1,
            self.DA_HUY: 1,
            self.DA_XAC_NHAN: 2,
            self.DANG_THUE: 4,
            self.HOAN_TAT: 5,
        }
        return thu_tu[self.trang_thai]

    @property
    def ten_thiet_bi(self):
        """Tên các dòng máy trong đơn, ví dụ 'Canon EOS R50 (số lượng 1)'."""
        cac_dong = list(self.cac_chi_tiet.all())
        if not cac_dong:
            return self.thiet_bi.ten
        return ', '.join(f'{dong.thiet_bi.ten} (số lượng {dong.so_luong})' for dong in cac_dong)


# ===========================================================================
# 2. CHI TIẾT ĐƠN VÀ MÁY ĐƯỢC GIỮ
# ===========================================================================

class ChiTietDonThue(models.Model):
    """Một dòng máy trong đơn. Giá được chốt lúc đặt, không đổi khi bảng giá thay đổi."""

    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_chi_tiet')
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.PROTECT)
    so_luong = models.PositiveIntegerField('Số lượng', default=1)
    don_gia = models.PositiveIntegerField('Đơn giá lúc đặt thuê')
    tien_coc_don_vi = models.PositiveIntegerField('Tiền cọc mỗi máy', default=0)
    cach_tinh_gia = models.TextField('Cách tính giá', blank=True)

    class Meta:
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(fields=['don', 'thiet_bi'], name='mot_dong_moi_thiet_bi'),
            models.CheckConstraint(condition=models.Q(so_luong__gt=0), name='so_luong_thue_duong'),
        ]

    @property
    def thanh_tien(self):
        return self.so_luong * self.don_gia


class PhanBoMay(models.Model):
    """Chiếc máy cụ thể (số sê-ri) được giữ cho một dòng của đơn."""

    chi_tiet = models.ForeignKey(ChiTietDonThue, on_delete=models.CASCADE, related_name='cac_phan_bo')
    may = models.ForeignKey(May, on_delete=models.PROTECT, related_name='cac_phan_bo')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['chi_tiet', 'may'], name='may_trong_dong_duy_nhat'),
        ]


# ===========================================================================
# 3. GIAO DỊCH TIỀN
# ===========================================================================

class GiaoDich(models.Model):
    """Một lần thu hoặc trả tiền gắn với đơn thuê."""

    DAT_COC = 'dat_coc'
    THANH_TOAN = 'thanh_toan'
    HOAN_COC = 'hoan_coc'
    PHU_THU = 'phu_thu'
    LOAI = [
        (DAT_COC, 'Đặt cọc'),
        (THANH_TOAN, 'Thanh toán tiền thuê'),
        (HOAN_COC, 'Hoàn cọc'),
        (PHU_THU, 'Thu thêm phụ thu / đền bù'),
    ]

    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_giao_dich')
    loai = models.CharField(max_length=20, choices=LOAI)
    so_tien = models.PositiveIntegerField('Số tiền')
    phuong_thuc = models.CharField(max_length=20, choices=DonThue.PHUONG_THUC_TIEN, default='tien_mat')
    # Nhân viên ghi nhận; cọc online do khách tự trả nên để trống
    nguoi_xac_nhan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cac_giao_dich_da_ghi',
    )
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']
        verbose_name = 'Giao dịch'
        verbose_name_plural = 'Giao dịch'


# ===========================================================================
# 4. THÔNG BÁO
# ===========================================================================

class ThongBao(models.Model):
    """Thông báo gửi cho người dùng khi đơn thuê hoặc phản hồi thay đổi."""

    nguoi_nhan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cac_thong_bao',
    )
    tieu_de = models.CharField(max_length=150, default='Cập nhật đơn thuê')
    noi_dung = models.CharField(max_length=255)
    don = models.ForeignKey(DonThue, on_delete=models.SET_NULL, null=True, blank=True)
    da_doc = models.BooleanField(default=False)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Thông báo'


# ===========================================================================
# 5. SỰ CỐ MÁY
# ===========================================================================

class SuCo(models.Model):
    """
    Sự cố của một chiếc máy thuộc đơn thuê (hỏng hóc, rơi vỡ, thiếu phụ kiện...).

    Nhân viên ghi nhận kèm mức độ và ảnh chụp chỗ hỏng.
    Lỗi nặng thì máy được chuyển sang "Bảo trì" để không cho thuê tiếp.
    """

    NHE = 'nhe'
    NANG = 'nang'
    MUC_DO = [
        (NHE, 'Lỗi nhẹ'),
        (NANG, 'Lỗi nặng'),
    ]

    CHO_XU_LY = 'cho_xu_ly'
    DA_XU_LY = 'da_xu_ly'
    TRANG_THAI = [
        (CHO_XU_LY, 'Chờ xử lý'),
        (DA_XU_LY, 'Đã xử lý'),
    ]

    don = models.ForeignKey(DonThue, on_delete=models.CASCADE, related_name='cac_su_co')
    may = models.ForeignKey(May, on_delete=models.PROTECT, related_name='cac_su_co')
    muc_do = models.CharField('Mức độ', max_length=10, choices=MUC_DO, default=NHE)
    mo_ta = models.TextField('Mô tả sự cố')
    trang_thai = models.CharField('Trạng thái', max_length=20, choices=TRANG_THAI, default=CHO_XU_LY)
    ket_qua_xu_ly = models.TextField('Kết quả xử lý', blank=True)
    nhan_vien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cac_su_co_da_ghi',
    )
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']
        verbose_name = 'Sự cố'
        verbose_name_plural = 'Sự cố'

    def __str__(self):
        return f'{self.don.ma} - {self.may.so_seri}'


class AnhSuCo(models.Model):
    """Ảnh chụp chỗ hỏng của máy, một sự cố có thể có nhiều ảnh."""

    su_co = models.ForeignKey(SuCo, on_delete=models.CASCADE, related_name='cac_anh')
    anh = models.ImageField('Ảnh máy hỏng', upload_to='su_co/')
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ngay_tao']

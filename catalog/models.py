"""
Các bảng dữ liệu của app catalog (thiết bị và dịch vụ cho thuê).

    LoaiThietBi : danh mục thiết bị (Mirrorless, Mirrorless cổ điển, Compact)
    ThietBi     : một dòng máy cho thuê, ví dụ Canon EOS R50 (UC-2)
    May         : một chiếc máy vật lý của dòng máy, phân biệt bằng số sê-ri
    GoiThue     : gói thuê theo thời lượng: 6 giờ, 1 ngày, 2 ngày... (UC-3)
    GiaThue     : giá của một dòng máy theo một gói thuê (UC-3.4)
    MaGiamGia   : mã giảm giá do chủ cửa hàng thiết lập
"""
from django.db import models
from django.utils import timezone


# ===========================================================================
# 1. THIẾT BỊ
# ===========================================================================

class LoaiThietBi(models.Model):
    """Danh mục thiết bị."""

    ma = models.SlugField('Mã danh mục', max_length=30, unique=True)
    ten = models.CharField('Tên danh mục', max_length=100, unique=True)

    class Meta:
        ordering = ['ten']
        verbose_name = 'Danh mục thiết bị'
        verbose_name_plural = 'Danh mục thiết bị'

    def __str__(self):
        return self.ten


class ThietBi(models.Model):
    """Một dòng máy ảnh cho thuê, ví dụ Canon EOS M50."""

    LOAI = [
        ('mirrorless', 'Mirrorless'),
        ('mirrorless_co_dien', 'Mirrorless cổ điển'),
        ('compact', 'Compact'),
    ]

    # ----- Thông tin chung -----
    ma = models.CharField('Mã thiết bị', max_length=20, unique=True)
    ten = models.CharField('Tên thiết bị', max_length=100)
    hang = models.CharField('Hãng', max_length=50)
    loai = models.CharField('Danh mục', max_length=30, choices=LOAI, default='mirrorless')
    danh_muc = models.ForeignKey(
        LoaiThietBi,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='Danh mục thiết bị',
        related_name='cac_thiet_bi',
    )

    # ----- Mô tả hiển thị cho khách -----
    thong_so = models.CharField('Thông số kỹ thuật', max_length=200, blank=True)
    mo_ta = models.CharField('Mô tả ngắn', max_length=255, blank=True)
    phu_hop = models.CharField('Phù hợp với', max_length=255, blank=True)
    anh = models.ImageField('Ảnh thiết bị', upload_to='thietbi/', blank=True)
    huong_dan = models.TextField('Hướng dẫn sử dụng', blank=True)
    video_huong_dan = models.URLField('Liên kết video hướng dẫn', blank=True)

    # ----- Tiền cọc và đền bù -----
    tien_coc = models.PositiveIntegerField('Tiền cọc (đồng)', default=700_000)
    gia_tri_den_bu = models.PositiveIntegerField('Giá trị đền bù 100% (đồng)', default=0)

    ngung_cung_cap = models.BooleanField('Ngừng cung cấp thiết bị này', default=False)

    class Meta:
        ordering = ['ten']
        verbose_name = 'Thiết bị'
        verbose_name_plural = 'Thiết bị'

    def __str__(self):
        return self.ten

    def so_may(self):
        return self.cac_may.count()

    def so_may_san_sang(self):
        return self.cac_may.filter(tinh_trang=May.SAN_SANG).count()

    def so_may_dang_thue(self):
        return self.cac_may.filter(tinh_trang=May.DANG_THUE).count()

    def gia_thap_nhat(self):
        """Giá rẻ nhất trong các gói đang cung cấp, dùng để hiện 'Từ ...đ'."""
        return self.cac_gia.filter(goi_thue__dang_cung_cap=True).order_by('gia').first()

    def tinh_trang_hien_thi(self):
        if self.ngung_cung_cap:
            return 'Ngừng cung cấp'
        if self.so_may_san_sang() > 0:
            return 'Sẵn sàng cho thuê'
        return 'Hết máy trống'


class May(models.Model):
    """Một chiếc máy vật lý, phân biệt bằng số sê-ri."""

    SAN_SANG = 'san_sang'
    DANG_THUE = 'dang_thue'
    BAO_TRI = 'bao_tri'
    HU_HONG = 'hu_hong'
    MAT_MAY = 'mat_may'
    TINH_TRANG = [
        (SAN_SANG, 'Sẵn sàng'),
        (DANG_THUE, 'Đang thuê'),
        (BAO_TRI, 'Bảo trì'),
        (HU_HONG, 'Hư hỏng'),
        (MAT_MAY, 'Mất máy'),
    ]

    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, related_name='cac_may')
    so_seri = models.CharField('Số sê-ri', max_length=50, unique=True)
    tinh_trang = models.CharField('Tình trạng', max_length=20, choices=TINH_TRANG, default=SAN_SANG)
    ngay_mua = models.DateField('Ngày mua / nhập máy', null=True, blank=True)

    class Meta:
        ordering = ['so_seri']
        verbose_name = 'Máy'
        verbose_name_plural = 'Máy'

    def __str__(self):
        return self.so_seri


# ===========================================================================
# 2. GÓI THUÊ VÀ GIÁ THUÊ
# ===========================================================================

class GoiThue(models.Model):
    """Gói thuê theo thời lượng. Gói tùy chỉnh cho khách tự chọn giờ, hệ thống tự tính giá."""

    ten = models.CharField('Tên gói', max_length=50, unique=True)
    so_gio_toi_da = models.PositiveIntegerField('Thời lượng tối đa (giờ)')
    mo_ta = models.CharField('Mô tả', max_length=255, blank=True)
    dang_cung_cap = models.BooleanField('Đang cung cấp', default=True)
    tuy_chinh = models.BooleanField('Cho phép tùy chỉnh thời gian và tự tính giá', default=False)

    class Meta:
        ordering = ['so_gio_toi_da']
        verbose_name = 'Gói thuê'
        verbose_name_plural = 'Gói thuê'

    def __str__(self):
        return self.ten


class GiaThue(models.Model):
    """Giá thuê của một thiết bị theo một gói (UC-3.4)."""

    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, related_name='cac_gia')
    goi_thue = models.ForeignKey(GoiThue, on_delete=models.CASCADE, related_name='cac_gia')
    gia = models.PositiveIntegerField('Giá thuê (đồng)')

    class Meta:
        ordering = ['goi_thue__so_gio_toi_da']
        constraints = [
            models.UniqueConstraint(fields=['thiet_bi', 'goi_thue'], name='mot_gia_moi_goi'),
        ]
        verbose_name = 'Giá thuê'
        verbose_name_plural = 'Giá thuê'

    def __str__(self):
        return f'{self.thiet_bi} - {self.goi_thue}: {self.gia}'


# ===========================================================================
# 3. MÃ GIẢM GIÁ
# ===========================================================================

class MaGiamGia(models.Model):
    """Mã giảm giá do chủ cửa hàng thiết lập: giảm theo phần trăm hoặc số tiền cố định."""

    PHAN_TRAM = 'phan_tram'
    SO_TIEN = 'so_tien'
    LOAI = [
        (PHAN_TRAM, 'Phần trăm'),
        (SO_TIEN, 'Số tiền cố định'),
    ]

    ma = models.CharField('Mã voucher', max_length=20, unique=True)
    loai = models.CharField('Loại giảm', max_length=20, choices=LOAI, default=PHAN_TRAM)
    gia_tri = models.PositiveIntegerField('Giá trị')
    so_luot = models.PositiveIntegerField('Số lượt còn lại', default=10)
    dang_ap_dung = models.BooleanField('Đang áp dụng', default=True)
    ngay_bat_dau = models.DateTimeField('Bắt đầu áp dụng', null=True, blank=True)
    ngay_ket_thuc = models.DateTimeField('Kết thúc áp dụng', null=True, blank=True)

    class Meta:
        verbose_name = 'Mã giảm giá'
        verbose_name_plural = 'Mã giảm giá'

    def __str__(self):
        return self.ma

    def tinh_giam(self, tien_thue):
        """Số tiền được giảm cho một đơn có tiền thuê cho trước (không vượt tiền thuê)."""
        if self.loai == self.PHAN_TRAM:
            return min(tien_thue * self.gia_tri // 100, tien_thue)
        return min(self.gia_tri, tien_thue)

    def co_hieu_luc(self, luc=None):
        """Mã còn dùng được: đang áp dụng, còn lượt và đang trong thời hạn."""
        luc = luc or timezone.now()
        con_han = (
            (self.ngay_bat_dau is None or self.ngay_bat_dau <= luc)
            and (self.ngay_ket_thuc is None or self.ngay_ket_thuc >= luc)
        )
        return self.dang_ap_dung and self.so_luot > 0 and con_han

    def da_co_don_dung(self):
        """Đã có đơn thuê nào dùng mã này chưa."""
        from rentals.models import DonThue  # import trong hàm để tránh vòng lặp import
        return DonThue.objects.filter(ma_giam_gia=self.ma).exists()

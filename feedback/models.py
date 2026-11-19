from django.db import models

from rentals.models import DonThue


class DanhGia(models.Model):
    """Phản hồi của khách cho một đơn đã hoàn tất (UC-4)."""

    CHO_XU_LY = 'cho_xu_ly'
    DA_DUYET = 'da_duyet'
    DA_AN = 'da_an'
    TRANG_THAI = [
        (CHO_XU_LY, 'Chờ xử lý'),
        (DA_DUYET, 'Đã duyệt'),
        (DA_AN, 'Đã ẩn'),
    ]
    SO_SAO = [(5, '5 sao'), (4, '4 sao'), (3, '3 sao'), (2, '2 sao'), (1, '1 sao')]

    # Mỗi đơn chỉ được đánh giá một lần
    don = models.OneToOneField(DonThue, on_delete=models.CASCADE, related_name='danh_gia')
    so_sao = models.PositiveSmallIntegerField('Đánh giá', choices=SO_SAO, default=5)
    noi_dung = models.TextField('Nội dung phản hồi')
    anh = models.ImageField('Ảnh feedback (tùy chọn)', upload_to='feedback/', blank=True)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default=CHO_XU_LY)
    tra_loi = models.TextField('Câu trả lời của cửa hàng', blank=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ngay_tao']

    def __str__(self):
        return f'{self.don.ma} - {self.so_sao} sao'

    @property
    def cac_sao(self):
        """Chuỗi sao để hiển thị, ví dụ ★★★★☆"""
        return '★' * self.so_sao + '☆' * (5 - self.so_sao)

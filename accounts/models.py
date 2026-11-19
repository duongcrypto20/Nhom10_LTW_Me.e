from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """Tài khoản người dùng, có thêm vai trò để phân quyền (UC-6.4)."""

    KHACH_HANG = 'khach_hang'
    NHAN_VIEN = 'nhan_vien'
    CHU_CUA_HANG = 'chu_cua_hang'
    VAI_TRO = [
        (KHACH_HANG, 'Khách hàng'),
        (NHAN_VIEN, 'Nhân viên'),
        (CHU_CUA_HANG, 'Chủ cửa hàng'),
    ]

    ho_ten = models.CharField('Họ tên', max_length=100)
    so_dien_thoai = models.CharField('Số điện thoại', max_length=15, blank=True)
    cccd = models.CharField('Số CCCD', max_length=12, blank=True)
    anh_dai_dien = models.ImageField('Ảnh đại diện', upload_to='avatars/', blank=True)
    vai_tro = models.CharField('Vai trò', max_length=20, choices=VAI_TRO, default=KHACH_HANG)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(Lower('email'), condition=~models.Q(email=''), name='email_khong_trung'),
            models.UniqueConstraint(fields=['so_dien_thoai'], condition=~models.Q(so_dien_thoai=''), name='sdt_khong_trung'),
        ]

    def __str__(self):
        return self.ho_ten or self.username

    @property
    def la_khach_hang(self):
        return self.vai_tro == self.KHACH_HANG

    @property
    def la_nhan_vien(self):
        """Chủ cửa hàng kế thừa toàn bộ quyền của nhân viên."""
        return self.vai_tro in (self.NHAN_VIEN, self.CHU_CUA_HANG)

    @property
    def la_chu_cua_hang(self):
        return self.vai_tro == self.CHU_CUA_HANG

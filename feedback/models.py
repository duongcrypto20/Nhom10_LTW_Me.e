from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from catalog.models import Camera
from rentals.models import RentalOrder

# KIỂM TRA ẢNH PHẢN HỒI
MAX_FEEDBACK_PHOTO_SIZE = 2 * 1024 * 1024  # 2 MB

def validate_photo_size(photo):
    """
    Giới hạn dung lượng ảnh phản hồi tối đa 2 MB.
    """
    if photo and photo.size > MAX_FEEDBACK_PHOTO_SIZE:
        raise ValidationError(
            "Ảnh phản hồi không được vượt quá 2 MB."
        )

# MODEL PHẢN HỒI KHÁCH HÀNG

class Feedback(models.Model):

    # KHÁCH HÀNG GỬI PHẢN HỒI
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
        verbose_name="Khách hàng",
    )

    # Mỗi đơn thuê chỉ được gửi một phản hồi
    order = models.OneToOneField(
        RentalOrder,
        on_delete=models.PROTECT,
        related_name="feedback",
        verbose_name="Đơn thuê",
    )

    # Máy ảnh được đánh giá
    camera = models.ForeignKey(
        Camera,
        on_delete=models.PROTECT,
        related_name="feedback_entries",
        verbose_name="Máy ảnh",
    )

    # NỘI DUNG ĐÁNH GIÁ

    rating = models.PositiveSmallIntegerField(
        "Đánh giá",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )

    content = models.TextField(
        "Nội dung phản hồi",
    )

    photo = models.ImageField(
        "Ảnh phản hồi",
        upload_to="feedback/%Y/%m/",
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ]
            ),
            validate_photo_size,
        ],
    )

    # QUẢN LÝ PHẢN HỒI - NHÂN VIÊN
    is_published = models.BooleanField(
        "Đã duyệt hiển thị",
        default=False,
    )

    # Nội dung nhân viên phản hồi khách hàng
    shop_reply = models.TextField(
        "Phản hồi của cửa hàng",
        blank=True,
    )
    created_at = models.DateTimeField(
        "Ngày gửi phản hồi",
        auto_now_add=True,
    )
    # CẤU HÌNH MODEL
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "phản hồi khách hàng"
        verbose_name_plural = "phản hồi khách hàng"

    def __str__(self):
        if self.camera_id:
            return f"{self.camera.name} · {self.rating}/5"

        return f"Phản hồi #{self.pk or 'mới'}"

    # KIỂM TRA DỮ LIỆU NGHIỆP VỤ
    def clean(self):
        """
        Quy tắc:

        1. Khách hàng chỉ được đánh giá đơn của mình.
        2. Máy được đánh giá phải đúng máy trong đơn.
        3. Chỉ đơn đã trả máy mới được đánh giá.
        4. Nội dung phải có ít nhất 10 ký tự.
        """

        super().clean()

        errors = []

        # Kiểm tra nội dung
        content = (self.content or "").strip()

        if content and len(content) < 10:
            errors.append(
                "Nội dung phản hồi phải có ít nhất 10 ký tự."
            )

        self.content = content

        # Kiểm tra liên kết đơn thuê
        if self.order_id:
            order = self.order

            # Đơn thuê phải thuộc khách hàng
            if self.user_id and order.user_id != self.user_id:
                errors.append(
                    "Đơn thuê không thuộc khách hàng này."
                )

            # Máy ảnh phải khớp với đơn thuê
            if self.camera_id and order.camera_id != self.camera_id:
                errors.append(
                    "Máy ảnh không khớp với đơn thuê."
                )

            # Chỉ được đánh giá sau khi trả máy
            if order.status != RentalOrder.Status.RETURNED:
                errors.append(
                    "Chỉ đơn thuê đã hoàn tất mới được đánh giá."
                )

        if errors:
            raise ValidationError(errors)

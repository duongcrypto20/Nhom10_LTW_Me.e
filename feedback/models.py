from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Camera
from rentals.models import RentalOrder


def validate_photo_size(photo):
    if photo.size > 2 * 1024 * 1024:
        raise ValidationError("Ảnh phản hồi không được vượt quá 2 MB.")


class Feedback(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
        verbose_name="Khách hàng",
    )
    order = models.OneToOneField(
        RentalOrder,
        on_delete=models.PROTECT,
        related_name="feedback",
        verbose_name="Đơn thuê",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.PROTECT,
        related_name="feedback_entries",
        verbose_name="Máy ảnh",
    )
    rating = models.PositiveSmallIntegerField(
        "Đánh giá",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    content = models.TextField("Nội dung")
    photo = models.ImageField(
        "Ảnh phản hồi",
        upload_to="feedback/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_photo_size],
    )
    is_published = models.BooleanField("Đã duyệt hiển thị", default=False)
    shop_reply = models.TextField("Phản hồi của cửa hàng", blank=True)
    created_at = models.DateTimeField("Ngày gửi", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "phản hồi khách hàng"
        verbose_name_plural = "phản hồi khách hàng"

    def __str__(self):
        return f"{self.camera} · {self.rating}/5"

    def clean(self):
        if self.order_id and self.user_id and self.order.user_id != self.user_id:
            raise ValidationError("Đơn thuê không thuộc khách hàng này.")
        if self.order_id and self.camera_id and self.order.camera_id != self.camera_id:
            raise ValidationError("Máy ảnh không khớp với đơn thuê.")
        if self.order_id and self.order.status != RentalOrder.Status.RETURNED:
            raise ValidationError("Chỉ đơn thuê đã hoàn tất mới được đánh giá.")

# Create your models here.

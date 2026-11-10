import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Camera, RentalRate


def new_order_code():
    return f"MEE-{uuid.uuid4().hex[:8].upper()}"


class RentalOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ cửa hàng xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        PREPARING = "preparing", "Đang chuẩn bị máy"
        RENTED = "rented", "Đang thuê"
        RETURNED = "returned", "Đã trả máy"
        REJECTED = "rejected", "Không thể nhận đơn"
        CANCELLED = "cancelled", "Đã hủy"

    class DepositStatus(models.TextChoices):
        UNCONFIRMED = "unconfirmed", "Chưa xác nhận mức cọc"
        DUE = "due", "Chờ nhận cọc"
        RECEIVED = "received", "Đã nhận cọc"
        REFUNDED = "refunded", "Đã hoàn cọc"
        DEDUCTED = "deducted", "Đã khấu trừ cọc"

    class DeliveryMethod(models.TextChoices):
        PICKUP = "pickup", "Nhận tại cửa hàng"
        DELIVERY = "delivery", "Giao/nhận theo địa chỉ"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rental_orders",
        verbose_name="Khách hàng",
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.PROTECT,
        related_name="rental_orders",
        verbose_name="Máy ảnh",
    )
    rate = models.ForeignKey(
        RentalRate,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
        verbose_name="Gói thuê",
    )
    order_code = models.CharField(
        "Mã đơn",
        max_length=20,
        unique=True,
        default=new_order_code,
        editable=False,
    )
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    start_at = models.DateTimeField("Thời gian nhận máy")
    end_at = models.DateTimeField("Thời gian trả dự kiến")
    quantity = models.PositiveSmallIntegerField(
        "Số lượng",
        default=1,
        validators=[MinValueValidator(1)],
    )
    rate_label = models.CharField("Tên gói tại thời điểm đặt", max_length=40)
    duration_hours = models.PositiveSmallIntegerField("Thời lượng thuê (giờ)")
    rental_total = models.PositiveIntegerField("Tiền thuê (đồng)")
    deposit_amount = models.PositiveIntegerField(
        "Tiền cọc được cửa hàng xác nhận",
        null=True,
        blank=True,
    )
    deposit_status = models.CharField(
        "Trạng thái cọc",
        max_length=20,
        choices=DepositStatus.choices,
        default=DepositStatus.UNCONFIRMED,
    )
    contact_name = models.CharField("Tên người nhận", max_length=150)
    contact_phone = models.CharField("Số điện thoại", max_length=20)
    contact_email = models.EmailField("Email", blank=True)
    delivery_method = models.CharField(
        "Hình thức nhận",
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
    )
    delivery_address = models.TextField("Địa chỉ giao nhận", blank=True)
    customer_note = models.TextField("Ghi chú của khách", blank=True)
    staff_note = models.TextField("Ghi chú nội bộ", blank=True)
    handover_at = models.DateTimeField("Thời gian giao máy", null=True, blank=True)
    returned_at = models.DateTimeField("Thời gian nhận trả máy", null=True, blank=True)
    return_method = models.CharField("Hình thức trả", max_length=100, blank=True)
    condition_out = models.TextField("Tình trạng máy khi giao", blank=True)
    condition_in = models.TextField("Tình trạng máy khi nhận trả", blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "đơn thuê"
        verbose_name_plural = "đơn thuê"
        indexes = [
            models.Index(fields=["camera", "start_at", "end_at", "status"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return self.order_code

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({"end_at": "Thời gian trả phải sau thời gian nhận."})
        if self.delivery_method == self.DeliveryMethod.DELIVERY and not self.delivery_address:
            raise ValidationError(
                {"delivery_address": "Vui lòng nhập địa chỉ giao nhận."}
            )

    @property
    def is_active_reservation(self):
        return self.status in {
            self.Status.PENDING,
            self.Status.CONFIRMED,
            self.Status.PREPARING,
            self.Status.RENTED,
        }

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.RENTED
            and self.returned_at is None
            and self.end_at < timezone.now()
        )


class RentalEvent(models.Model):
    order = models.ForeignKey(
        RentalOrder,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Đơn thuê",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Người thao tác",
    )
    title = models.CharField("Sự kiện", max_length=120)
    details = models.TextField("Chi tiết", blank=True)
    created_at = models.DateTimeField("Thời gian", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lịch sử đơn thuê"
        verbose_name_plural = "lịch sử đơn thuê"

    def __str__(self):
        return f"{self.order.order_code} · {self.title}"

# Create your models here.

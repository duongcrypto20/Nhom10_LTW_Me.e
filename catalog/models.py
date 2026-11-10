from django.db import models
from django.urls import reverse


class Camera(models.Model):
    class Brand(models.TextChoices):
        CANON = "Canon", "Canon"
        FUJIFILM = "Fujifilm", "Fujifilm"

    name = models.CharField("Tên máy", max_length=120, unique=True)
    slug = models.SlugField("Đường dẫn", max_length=140, unique=True)
    brand = models.CharField("Hãng", max_length=30, choices=Brand.choices)
    image = models.CharField(
        "Ảnh trong static/images/products",
        max_length=255,
        help_text="Đường dẫn tương đối trong thư mục static.",
    )
    description = models.TextField("Mô tả", blank=True)
    deposit_amount = models.PositiveIntegerField(
        "Tiền cọc đã được cửa hàng xác nhận",
        null=True,
        blank=True,
        help_text="Để trống cho đến khi cửa hàng xác nhận mức cọc cho đúng mẫu máy.",
    )
    available_units = models.PositiveSmallIntegerField(
        "Số máy có thể cho thuê",
        default=1,
        help_text="Cập nhật theo số máy vật lý thực tế.",
    )
    is_active = models.BooleanField("Đang kinh doanh", default=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật", auto_now=True)

    class Meta:
        ordering = ["brand", "name"]
        verbose_name = "máy ảnh"
        verbose_name_plural = "máy ảnh"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:detail", kwargs={"slug": self.slug})

    @property
    def lowest_rate(self):
        active_rates = [rate for rate in self.rates.all() if rate.is_active]
        return min(active_rates, key=lambda rate: rate.amount, default=None)


class RentalRate(models.Model):
    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name="rates",
        verbose_name="Máy ảnh",
    )
    label = models.CharField("Thời lượng", max_length=40)
    duration_hours = models.PositiveSmallIntegerField("Số giờ thuê")
    amount = models.PositiveIntegerField("Giá thuê (đồng)")
    sort_order = models.PositiveSmallIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang áp dụng", default=True)

    class Meta:
        ordering = ["sort_order", "duration_hours"]
        constraints = [
            models.UniqueConstraint(
                fields=["camera", "duration_hours"],
                name="unique_camera_rental_duration",
            )
        ]
        verbose_name = "mức giá thuê"
        verbose_name_plural = "bảng giá thuê"

    def __str__(self):
        return f"{self.camera} · {self.label}"

# Create your models here.

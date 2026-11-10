from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import models, transaction
from django.utils import timezone


class CustomerProfile(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Khách hàng"
        STAFF = "staff", "Nhân viên"
        MANAGER = "manager", "Quản lý"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField("Số điện thoại", max_length=20, blank=True)
    role = models.CharField(
        "Vai trò",
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    class Meta:
        verbose_name = "hồ sơ khách hàng"
        verbose_name_plural = "hồ sơ khách hàng"

    def __str__(self):
        return self.user.get_full_name() or self.user.email or self.user.get_username()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_access()

    def sync_access(self):
        """Keep the simple application role aligned with Django admin access."""
        user = self.user
        role_groups = Group.objects.filter(name__in=["ME.E Nhân viên", "ME.E Chủ cửa hàng"])
        if user.is_superuser:
            user.groups.remove(*role_groups)
            return

        is_staff = self.role in {self.Role.STAFF, self.Role.MANAGER}
        if user.is_staff != is_staff:
            type(user).objects.filter(pk=user.pk).update(is_staff=is_staff)
            user.is_staff = is_staff

        user.groups.remove(*role_groups)
        if self.role == self.Role.CUSTOMER:
            return

        group_name = "ME.E Nhân viên" if self.role == self.Role.STAFF else "ME.E Chủ cửa hàng"
        group, _ = Group.objects.get_or_create(name=group_name)
        app_labels = ["catalog", "rentals", "feedback"]
        if self.role == self.Role.MANAGER:
            permissions = Permission.objects.filter(
                content_type__app_label__in=[*app_labels, "customers", "auth"]
            )
        else:
            permissions = Permission.objects.filter(
                content_type__app_label__in=app_labels
            ).exclude(codename__startswith="delete_")
        group.permissions.set(permissions)
        user.groups.add(group)


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_addresses",
    )
    label = models.CharField("Tên địa chỉ", max_length=40)
    recipient = models.CharField("Người nhận", max_length=100)
    phone = models.CharField("Số điện thoại nhận", max_length=20)
    street = models.CharField("Địa chỉ chi tiết", max_length=220)
    district = models.CharField("Quận/huyện", max_length=100)
    city = models.CharField("Tỉnh/thành phố", max_length=100)
    is_default = models.BooleanField("Địa chỉ mặc định", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "địa chỉ"
        verbose_name_plural = "địa chỉ"

    def __str__(self):
        return f"{self.label} — {self.district}, {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(user=self.user, is_default=True).exclude(
                    pk=self.pk
                ).update(is_default=False)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField("Tiêu đề", max_length=160)
    message = models.TextField("Nội dung")
    order_id = models.PositiveBigIntegerField("Mã đơn thuê", null=True, blank=True)
    created_at = models.DateTimeField("Thời gian tạo", auto_now_add=True)
    read_at = models.DateTimeField("Đã đọc lúc", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "thông báo"
        verbose_name_plural = "thông báo"

    def __str__(self):
        return self.title

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

# Create your models here.

from django.contrib import admin, messages
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from customers.models import Notification

from .models import RentalEvent, RentalOrder
from .services import has_capacity


class RentalEventInline(admin.TabularInline):
    model = RentalEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "title", "details", "created_at")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class RentalOrderAdminForm(forms.ModelForm):
    class Meta:
        model = RentalOrder
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned

        old_status = RentalOrder.objects.get(pk=self.instance.pk).status
        new_status = cleaned.get("status")
        allowed = {
            RentalOrder.Status.PENDING: {
                RentalOrder.Status.CONFIRMED,
                RentalOrder.Status.REJECTED,
                RentalOrder.Status.CANCELLED,
            },
            RentalOrder.Status.CONFIRMED: {
                RentalOrder.Status.PREPARING,
                RentalOrder.Status.REJECTED,
            },
            RentalOrder.Status.PREPARING: {
                RentalOrder.Status.RENTED,
                RentalOrder.Status.REJECTED,
            },
            RentalOrder.Status.RENTED: {RentalOrder.Status.RETURNED},
            RentalOrder.Status.RETURNED: set(),
            RentalOrder.Status.REJECTED: set(),
            RentalOrder.Status.CANCELLED: set(),
        }
        if new_status != old_status and new_status not in allowed[old_status]:
            raise ValidationError("Trạng thái đơn không thể chuyển theo quy trình hiện tại.")
        if (
            new_status in {
                RentalOrder.Status.CONFIRMED,
                RentalOrder.Status.PREPARING,
                RentalOrder.Status.RENTED,
            }
            and new_status != old_status
            and not has_capacity(
                self.instance.camera,
                self.instance.start_at,
                self.instance.end_at,
                self.instance.quantity,
                exclude_order_id=self.instance.pk,
            )
        ):
            self.add_error(
                "status",
                "Lịch máy đang trùng với đơn thuê khác; hãy kiểm tra lại lịch trước khi xác nhận.",
            )
        if new_status == RentalOrder.Status.RENTED and old_status != new_status:
            if not cleaned.get("condition_out"):
                self.add_error("condition_out", "Ghi nhận tình trạng máy trước khi giao.")
        if new_status == RentalOrder.Status.RETURNED and old_status != new_status:
            if not cleaned.get("condition_in"):
                self.add_error("condition_in", "Ghi nhận tình trạng máy khi nhận trả.")
            if not cleaned.get("return_method"):
                self.add_error("return_method", "Ghi nhận hình thức trả máy.")
        return cleaned


@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    form = RentalOrderAdminForm
    list_display = (
        "order_code",
        "user",
        "camera",
        "start_at",
        "end_at",
        "status",
        "deposit_status",
    )
    list_filter = ("status", "deposit_status", "delivery_method", "created_at")
    search_fields = ("order_code", "user__email", "contact_name", "contact_phone")
    readonly_fields = (
        "order_code",
        "user",
        "camera",
        "rate",
        "start_at",
        "end_at",
        "quantity",
        "rate_label",
        "duration_hours",
        "rental_total",
        "contact_name",
        "contact_phone",
        "contact_email",
        "delivery_method",
        "delivery_address",
        "customer_note",
        "created_at",
        "updated_at",
    )
    inlines = [RentalEventInline]
    date_hierarchy = "start_at"
    fieldsets = (
        ("Đơn thuê", {"fields": ("order_code", "user", "camera", "rate", "status")}),
        ("Lịch và giá", {
            "fields": (
                "start_at",
                "end_at",
                "quantity",
                "rate_label",
                "duration_hours",
                "rental_total",
            )
        }),
        ("Khách hàng và giao nhận", {
            "fields": (
                "contact_name",
                "contact_phone",
                "contact_email",
                "delivery_method",
                "delivery_address",
                "customer_note",
            )
        }),
        ("Cọc và kiểm tra máy", {
            "fields": (
                "deposit_amount",
                "deposit_status",
                "handover_at",
                "condition_out",
                "returned_at",
                "return_method",
                "condition_in",
                "staff_note",
            )
        }),
        ("Thời gian hệ thống", {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = RentalOrder.objects.get(pk=obj.pk).status
        if obj.status == RentalOrder.Status.RENTED and not obj.handover_at:
            obj.handover_at = timezone.now()
        if obj.status == RentalOrder.Status.RETURNED and not obj.returned_at:
            obj.returned_at = timezone.now()
        super().save_model(request, obj, form, change)

        if not change:
            title = "Đơn thuê đã được tạo"
            details = f"Đơn {obj.order_code} đã được tạo trong trang quản trị."
        elif previous_status != obj.status:
            title = f"Trạng thái đơn: {obj.get_status_display()}"
            details = obj.staff_note or obj.get_status_display()
            Notification.objects.create(
                user=obj.user,
                title=title,
                message=f"Đơn {obj.order_code}: {details}",
                order_id=obj.pk,
            )
        else:
            return

        RentalEvent.objects.create(
            order=obj,
            actor=request.user,
            title=title,
            details=details,
        )
        self.message_user(
            request,
            "Đơn thuê và lịch sử xử lý đã được lưu.",
            level=messages.SUCCESS,
        )

    def has_add_permission(self, request):
        return False


@admin.register(RentalEvent)
class RentalEventAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "actor", "created_at")
    list_filter = ("created_at",)
    search_fields = ("order__order_code", "title", "details")
    readonly_fields = ("order", "actor", "title", "details", "created_at")

    def has_add_permission(self, request):
        return False

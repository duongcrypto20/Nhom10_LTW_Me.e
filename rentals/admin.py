
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone

from customers.models import Notification

from .models import RentalEvent, RentalOrder
from .services import (
    ALLOWED_DEPOSIT_TRANSITIONS,
    ALLOWED_TRANSITIONS,
    BookingConflict,
    has_capacity,
    update_order_deposit,
    update_order_status,
)


# HIỂN THỊ LỊCH SỬ ĐƠN THUÊ
class RentalEventInline(admin.TabularInline):
    model = RentalEvent
    extra = 0
    can_delete = False

    readonly_fields = (
        "actor",
        "title",
        "details",
        "created_at",
    )

    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


# BIỂU MẪU XỬ LÝ ĐƠN THUÊ
class RentalOrderAdminForm(forms.ModelForm):
    customer_message = forms.CharField(
        label="Lời nhắn gửi khách hàng",
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Nhập nội dung thông báo cho khách hàng "
                    "khi xử lý đơn..."
                ),
            }
        ),
        help_text=(
            "Nội dung này có thể được gửi qua thông báo. "
            "Không nhập thông tin nội bộ của cửa hàng."
        ),
    )

    class Meta:
        model = RentalOrder
        fields = "__all__"

        widgets = {
            "staff_note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Ghi chú chỉ dành cho nội bộ...",
                }
            ),
            "condition_out": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Ghi nhận tình trạng máy và phụ kiện khi giao..."
                    ),
                }
            ),
            "condition_in": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Ghi nhận tình trạng máy và phụ kiện khi nhận trả..."
                    ),
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()

        if not self.instance.pk:
            return cleaned

        old_order = RentalOrder.objects.get(
            pk=self.instance.pk
        )

        new_status = cleaned.get("status")
        new_deposit_status = cleaned.get("deposit_status")
        new_deposit_amount = cleaned.get("deposit_amount")

        customer_message = (
            cleaned.get("customer_message") or ""
        ).strip()

        if new_status is None or new_deposit_status is None:
            return cleaned

        if new_status != old_order.status:
            allowed_statuses = ALLOWED_TRANSITIONS.get(
                old_order.status,
                set(),
            )

            if new_status not in allowed_statuses:
                self.add_error(
                    "status",
                    "Không thể chuyển trạng thái đơn thuê "
                    "theo quy trình hiện tại.",
                )

            if new_status in {
                RentalOrder.Status.CONFIRMED,
                RentalOrder.Status.PREPARING,
                RentalOrder.Status.RENTED,
            }:
                camera = old_order.camera

                if not has_capacity(
                    camera,
                    old_order.start_at,
                    old_order.end_at,
                    old_order.quantity,
                    exclude_order_id=old_order.pk,
                ):
                    self.add_error(
                        "status",
                        "Lịch máy đang trùng hoặc không đủ số lượng. "
                        "Vui lòng kiểm tra lại.",
                    )

            if new_status == RentalOrder.Status.CONFIRMED:
                if (
                    new_deposit_status
                    == RentalOrder.DepositStatus.UNCONFIRMED
                    or new_deposit_amount is None
                    or new_deposit_amount <= 0
                ):
                    self.add_error(
                        "status",
                        "Cần xác nhận mức tiền cọc "
                        "trước khi xác nhận đơn thuê.",
                    )

            if new_status == RentalOrder.Status.RENTED:
                if not (
                    cleaned.get("condition_out") or ""
                ).strip():
                    self.add_error(
                        "condition_out",
                        "Vui lòng ghi nhận tình trạng máy "
                        "trước khi bàn giao.",
                    )

            if new_status == RentalOrder.Status.RETURNED:
                if not (
                    cleaned.get("condition_in") or ""
                ).strip():
                    self.add_error(
                        "condition_in",
                        "Vui lòng ghi nhận tình trạng máy "
                        "khi nhận trả.",
                    )

                if not (
                    cleaned.get("return_method") or ""
                ).strip():
                    self.add_error(
                        "return_method",
                        "Vui lòng nhập hình thức trả máy.",
                    )

            if new_status in {
                RentalOrder.Status.REJECTED,
                RentalOrder.Status.CANCELLED,
            } and not customer_message:
                self.add_error(
                    "customer_message",
                    "Vui lòng nhập lý do từ chối "
                    "hoặc hủy đơn để thông báo cho khách hàng.",
                )

        if new_deposit_status != old_order.deposit_status:
            allowed_deposit_statuses = (
                ALLOWED_DEPOSIT_TRANSITIONS.get(
                    old_order.deposit_status,
                    set(),
                )
            )

            if new_deposit_status not in allowed_deposit_statuses:
                self.add_error(
                    "deposit_status",
                    "Không thể chuyển trạng thái tiền cọc "
                    "theo quy trình hiện tại.",
                )

        if old_order.deposit_status in {
            RentalOrder.DepositStatus.RECEIVED,
            RentalOrder.DepositStatus.REFUNDED,
            RentalOrder.DepositStatus.DEDUCTED,
        }:
            if new_deposit_amount != old_order.deposit_amount:
                self.add_error(
                    "deposit_amount",
                    "Không thể thay đổi mức tiền cọc "
                    "sau khi đã ghi nhận nhận cọc.",
                )

        if new_deposit_status != RentalOrder.DepositStatus.UNCONFIRMED:
            if (
                new_deposit_amount is None
                or new_deposit_amount <= 0
            ):
                self.add_error(
                    "deposit_amount",
                    "Vui lòng nhập mức tiền cọc lớn hơn 0.",
                )

        if new_deposit_status == RentalOrder.DepositStatus.DEDUCTED:
            if (
                new_deposit_status != old_order.deposit_status
                and not customer_message
            ):
                self.add_error(
                    "customer_message",
                    "Vui lòng nhập lý do khấu trừ tiền cọc.",
                )

        if new_status in {
            RentalOrder.Status.REJECTED,
            RentalOrder.Status.CANCELLED,
            RentalOrder.Status.RETURNED,
        } and new_deposit_status in {
            RentalOrder.DepositStatus.DUE,
            RentalOrder.DepositStatus.RECEIVED,
        }:
            if (
                new_deposit_status != old_order.deposit_status
                or new_status != old_order.status
            ):
                self.add_error(
                    "deposit_status",
                    "Đơn đã kết thúc không được "
                    "tiếp tục yêu cầu hoặc nhận tiền cọc. "
                    "Hãy xử lý trạng thái cọc phù hợp trước.",
                )

        return cleaned


# QUẢN LÝ ĐƠN THUÊ
@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    form = RentalOrderAdminForm

    list_display = (
        "order_code",
        "user",
        "camera",
        "start_at",
        "end_at",
        "quantity",
        "status",
        "deposit_status",
        "created_at",
    )

    list_filter = (
        "status",
        "deposit_status",
        "delivery_method",
        "created_at",
    )

    search_fields = (
        "order_code",
        "user__email",
        "contact_name",
        "contact_phone",
        "camera__name",
    )

    list_select_related = (
        "user",
        "camera",
    )

    ordering = ("-created_at",)

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
        "handover_at",
        "returned_at",
        "created_at",
        "updated_at",
    )

    inlines = [RentalEventInline]

    date_hierarchy = "start_at"

    actions = None

    fieldsets = (
        (
            "Thông tin đơn thuê",
            {
                "fields": (
                    "order_code",
                    "user",
                    "camera",
                    "rate",
                    "status",
                ),
            },
        ),
        (
            "Lịch thuê và giá",
            {
                "fields": (
                    "start_at",
                    "end_at",
                    "quantity",
                    "rate_label",
                    "duration_hours",
                    "rental_total",
                ),
            },
        ),
        (
            "Thông tin khách hàng và giao nhận",
            {
                "fields": (
                    "contact_name",
                    "contact_phone",
                    "contact_email",
                    "delivery_method",
                    "delivery_address",
                    "customer_note",
                ),
            },
        ),
        (
            "Quản lý tiền cọc",
            {
                "fields": (
                    "deposit_amount",
                    "deposit_status",
                ),
            },
        ),
        (
            "Bàn giao và nhận trả máy",
            {
                "fields": (
                    "handover_at",
                    "condition_out",
                    "returned_at",
                    "return_method",
                    "condition_in",
                ),
            },
        ),
        (
            "Ghi chú và thông báo",
            {
                "fields": (
                    "staff_note",
                    "customer_message",
                ),
            },
        ),
        (
            "Thời gian hệ thống",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            return

        old_order = RentalOrder.objects.get(pk=obj.pk)

        new_status = obj.status
        new_deposit_status = obj.deposit_status
        new_deposit_amount = obj.deposit_amount

        customer_message = (
            form.cleaned_data.get("customer_message") or ""
        ).strip()

        status_changed = new_status != old_order.status

        deposit_changed = (
            new_deposit_status != old_order.deposit_status
            or new_deposit_amount != old_order.deposit_amount
        )

        private_fields = (
            "staff_note",
            "condition_out",
            "condition_in",
            "return_method",
        )

        private_changes = {
            field: getattr(obj, field)
            for field in private_fields
            if getattr(obj, field) != getattr(old_order, field)
        }

        def update_status():
            update_order_status(
                order_id=obj.pk,
                actor=request.user,
                new_status=new_status,
                customer_message=customer_message,
                condition_out=obj.condition_out,
                condition_in=obj.condition_in,
                return_method=obj.return_method,
                staff_note=obj.staff_note,
            )

        def update_deposit():
            update_order_deposit(
                order_id=obj.pk,
                actor=request.user,
                new_status=new_deposit_status,
                amount=new_deposit_amount,
                customer_message=customer_message,
            )

        deposit_after_status = (
            status_changed
            and new_status == RentalOrder.Status.RETURNED
            and new_deposit_status in {
                RentalOrder.DepositStatus.REFUNDED,
                RentalOrder.DepositStatus.DEDUCTED,
            }
        )

        if deposit_after_status:
            if status_changed:
                update_status()

            if deposit_changed:
                update_deposit()

        else:
            if deposit_changed:
                update_deposit()

            if status_changed:
                update_status()

        if not status_changed and private_changes:
            RentalOrder.objects.filter(
                pk=obj.pk
            ).update(
                **private_changes,
                updated_at=timezone.now(),
            )

            RentalEvent.objects.create(
                order_id=obj.pk,
                actor=request.user,
                title="Cập nhật thông tin nội bộ",
                details=(
                    "Nhân viên đã cập nhật ghi chú "
                    "hoặc thông tin kiểm tra máy."
                ),
            )

        if (
            customer_message
            and not status_changed
            and not deposit_changed
        ):
            Notification.objects.create(
                user=old_order.user,
                title="Thông báo từ cửa hàng",
                message=(
                    f"Đơn {old_order.order_code}: "
                    f"{customer_message}"
                ),
                order_id=old_order.pk,
            )

            RentalEvent.objects.create(
                order_id=old_order.pk,
                actor=request.user,
                title="Đã gửi lời nhắn cho khách hàng",
                details=customer_message,
            )

        obj.refresh_from_db()

        self.message_user(
            request,
            "Thông tin đơn thuê đã được cập nhật thành công.",
            level=messages.SUCCESS,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# QUẢN LÝ LỊCH SỬ ĐƠN THUÊ
@admin.register(RentalEvent)
class RentalEventAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "title",
        "actor",
        "created_at",
    )

    list_filter = ("created_at",)

    search_fields = (
        "order__order_code",
        "title",
        "details",
    )

    readonly_fields = (
        "order",
        "actor",
        "title",
        "details",
        "created_at",
    )

    ordering = ("-created_at",)

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

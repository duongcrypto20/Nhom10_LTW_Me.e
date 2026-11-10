from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from catalog.models import Camera
from customers.models import Notification

from .models import RentalEvent, RentalOrder


class BookingConflict(Exception):
    """Raised when a camera has no remaining units for the requested interval."""


def has_capacity(camera, start_at, end_at, quantity=1, exclude_order_id=None):
    reservations = RentalOrder.objects.filter(
        camera=camera,
        status__in=[
            RentalOrder.Status.PENDING,
            RentalOrder.Status.CONFIRMED,
            RentalOrder.Status.PREPARING,
            RentalOrder.Status.RENTED,
        ],
        start_at__lt=end_at,
    ).filter(
        Q(end_at__gt=start_at)
        | Q(
            status=RentalOrder.Status.RENTED,
            returned_at__isnull=True,
            end_at__lte=timezone.now(),
        )
    )
    if exclude_order_id is not None:
        reservations = reservations.exclude(pk=exclude_order_id)
    occupied = sum(
        order.quantity
        for order in reservations.only(
            "quantity", "start_at", "end_at", "returned_at", "status"
        )
        if order.returned_at is None or order.returned_at > start_at
    )
    return occupied + quantity <= camera.available_units


@transaction.atomic
def create_order(*, user, camera, rate, form_data):
    camera = Camera.objects.select_for_update().get(pk=camera.pk, is_active=True)
    if rate.camera_id != camera.id or not rate.is_active:
        raise BookingConflict("Gói thuê này không còn áp dụng.")

    start_at = form_data["start_at"]
    end_at = start_at + timedelta(hours=rate.duration_hours)
    quantity = form_data["quantity"]

    if not has_capacity(camera, start_at, end_at, quantity):
        raise BookingConflict("Máy không còn trống trong toàn bộ khoảng thời gian này.")

    profile = getattr(user, "customer_profile", None)
    if not profile or not profile.phone.strip():
        raise BookingConflict("Hãy cập nhật số điện thoại trong tài khoản trước khi đặt thuê.")

    order = RentalOrder(
        user=user,
        camera=camera,
        rate=rate,
        start_at=start_at,
        end_at=end_at,
        quantity=quantity,
        rate_label=rate.label,
        duration_hours=rate.duration_hours,
        rental_total=rate.amount * quantity,
        contact_name=user.get_full_name() or user.get_username(),
        contact_phone=profile.phone if profile else "",
        contact_email=user.email,
        delivery_method=form_data["delivery_method"],
        delivery_address=form_data.get("delivery_address", "").strip(),
        customer_note=form_data.get("customer_note", "").strip(),
    )
    try:
        order.full_clean()
    except ValidationError as error:
        raise BookingConflict("Thông tin đơn thuê không hợp lệ. Hãy kiểm tra lại lịch và địa chỉ.") from error
    order.save()
    RentalEvent.objects.create(
        order=order,
        actor=user,
        title="Đã gửi yêu cầu thuê",
        details="Đơn đang chờ cửa hàng kiểm tra lịch và xác nhận tiền cọc.",
    )
    Notification.objects.create(
        user=user,
        title="Đã nhận yêu cầu thuê",
        message=(
            f"Cửa hàng đã nhận yêu cầu {order.order_code}. "
            "Đơn chỉ được xác nhận sau khi cửa hàng kiểm tra lịch và liên hệ bạn."
        ),
        order_id=order.pk,
    )
    return order

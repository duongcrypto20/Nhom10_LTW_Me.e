
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import Notification

from .models import RentalEvent, RentalOrder


# XỬ LÝ LỖI ĐẶT THUÊ
class BookingConflict(Exception):
    pass


# TRẠNG THÁI ĐƠN CHIẾM LỊCH MÁY
RESERVING_STATUSES = (
    RentalOrder.Status.PENDING,
    RentalOrder.Status.CONFIRMED,
    RentalOrder.Status.PREPARING,
    RentalOrder.Status.RENTED,
)


#CHUYỂN TRẠNG THÁI ĐƠN
ALLOWED_TRANSITIONS = {
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
    RentalOrder.Status.RENTED: {
        RentalOrder.Status.RETURNED,
    },
    RentalOrder.Status.RETURNED: set(),
    RentalOrder.Status.REJECTED: set(),
    RentalOrder.Status.CANCELLED: set(),
}


# QUY TẮC CHUYỂN TRẠNG THÁI CỌC
ALLOWED_DEPOSIT_TRANSITIONS = {
    RentalOrder.DepositStatus.UNCONFIRMED: {
        RentalOrder.DepositStatus.DUE,
    },
    RentalOrder.DepositStatus.DUE: {
        RentalOrder.DepositStatus.RECEIVED,
        RentalOrder.DepositStatus.UNCONFIRMED,
    },
    RentalOrder.DepositStatus.RECEIVED: {
        RentalOrder.DepositStatus.REFUNDED,
        RentalOrder.DepositStatus.DEDUCTED,
    },
    RentalOrder.DepositStatus.REFUNDED: set(),
    RentalOrder.DepositStatus.DEDUCTED: set(),
}


# KIỂM TRA QUYỀN XỬ LÝ ĐƠN
def _check_order_permission(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("rentals.change_rentalorder")
    ):
        raise PermissionDenied(
            "Bạn không có quyền xử lý đơn thuê."
        )


# GHI NHẬN LỊCH SỬ VÀ THÔNG BÁO
def _record_order_event(
    *,
    order,
    actor,
    title,
    message,
):
    RentalEvent.objects.create(
        order=order,
        actor=actor,
        title=title,
        details=message,
    )

    Notification.objects.create(
        user=order.user,
        title=title,
        message=f"Đơn {order.order_code}: {message}",
        order_id=order.pk,
    )


# KIỂM TRA SỐ LƯỢNG MÁY KHẢ DỤNG
def has_capacity(
    camera,
    start_at,
    end_at,
    quantity=1,
    exclude_order_id=None,
):
    if (
        start_at is None
        or end_at is None
        or end_at <= start_at
        or not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity < 1
    ):
        return False

    if quantity > camera.available_units:
        return False

    reservations = RentalOrder.objects.filter(
        camera_id=camera.pk,
        status__in=RESERVING_STATUSES,
        start_at__lt=end_at,
    ).filter(
        Q(end_at__gt=start_at)
        | Q(
            status=RentalOrder.Status.RENTED,
            returned_at__isnull=True,
        )
        | Q(
            status=RentalOrder.Status.RENTED,
            returned_at__gt=start_at,
        )
    )

    if exclude_order_id is not None:
        reservations = reservations.exclude(
            pk=exclude_order_id
        )

    events = []
    now = timezone.now()

    for order in reservations.only(
        "status",
        "start_at",
        "end_at",
        "quantity",
        "returned_at",
    ):
        reservation_start = order.start_at
        reservation_end = order.end_at

        if order.status == RentalOrder.Status.RENTED:
            if order.returned_at is not None:
                reservation_end = order.returned_at

            elif order.end_at <= now:
                reservation_end = end_at

        overlap_start = max(
            reservation_start,
            start_at,
        )

        overlap_end = min(
            reservation_end,
            end_at,
        )

        if overlap_start >= overlap_end:
            continue

        events.append(
            (overlap_start, order.quantity)
        )

        events.append(
            (overlap_end, -order.quantity)
        )

    events.sort(
        key=lambda event: (event[0], event[1])
    )

    occupied = 0

    for _, change in events:
        occupied += change

        if occupied + quantity > camera.available_units:
            return False

    return True


# TẠO ĐƠN THUÊ
@transaction.atomic
def create_order(
    *,
    user,
    camera,
    rate,
    form_data,
):
    if not user.is_authenticated or not user.is_active:
        raise BookingConflict(
            "Vui lòng đăng nhập để đặt thuê máy."
        )

    camera = Camera.objects.select_for_update().filter(
        pk=camera.pk,
        is_active=True,
    ).first()

    if camera is None:
        raise BookingConflict(
            "Máy ảnh này hiện không còn kinh doanh."
        )

    rate = RentalRate.objects.select_for_update().filter(
        pk=rate.pk,
        camera=camera,
        is_active=True,
    ).first()

    if rate is None:
        raise BookingConflict(
            "Gói thuê này không còn áp dụng."
        )

    start_at = form_data.get("start_at")
    quantity = form_data.get("quantity")

    if (
        start_at is None
        or timezone.is_naive(start_at)
        or start_at <= timezone.now()
    ):
        raise BookingConflict(
            "Thời gian nhận máy phải ở tương lai."
        )

    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or not 1 <= quantity <= 10
    ):
        raise BookingConflict(
            "Số lượng thuê phải từ 1 đến 10 máy."
        )

    if quantity > camera.available_units:
        raise BookingConflict(
            "Số lượng yêu cầu vượt quá số máy của cửa hàng."
        )

    if rate.duration_hours == 6:
        local_start = timezone.localtime(start_at)

        if (
            local_start.hour,
            local_start.minute,
        ) not in {(8, 0), (15, 0)}:
            raise BookingConflict(
                "Gói 6 giờ chỉ nhận máy lúc 08:00 hoặc 15:00."
            )

    end_at = start_at + timedelta(
        hours=rate.duration_hours
    )

    delivery_method = form_data.get("delivery_method")
    delivery_address = (
        form_data.get("delivery_address") or ""
    ).strip()

    customer_note = (
        form_data.get("customer_note") or ""
    ).strip()

    valid_delivery_methods = {
        RentalOrder.DeliveryMethod.PICKUP,
        RentalOrder.DeliveryMethod.DELIVERY,
    }

    if delivery_method not in valid_delivery_methods:
        raise BookingConflict(
            "Hình thức nhận máy không hợp lệ."
        )

    if (
        delivery_method == RentalOrder.DeliveryMethod.DELIVERY
        and not delivery_address
    ):
        raise BookingConflict(
            "Vui lòng nhập địa chỉ giao nhận."
        )

    if len(delivery_address) > 500:
        raise BookingConflict(
            "Địa chỉ giao nhận không được vượt quá 500 ký tự."
        )

    if len(customer_note) > 1000:
        raise BookingConflict(
            "Ghi chú không được vượt quá 1000 ký tự."
        )

    if not has_capacity(
        camera,
        start_at,
        end_at,
        quantity,
    ):
        raise BookingConflict(
            "Máy không còn đủ số lượng trong khoảng "
            "thời gian này. Vui lòng chọn lịch khác."
        )

    profile = getattr(
        user,
        "customer_profile",
        None,
    )

    if not profile or not profile.phone.strip():
        raise BookingConflict(
            "Hãy cập nhật số điện thoại trong tài khoản "
            "trước khi đặt thuê."
        )

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
        contact_name=(
            user.get_full_name()
            or user.get_username()
        ),
        contact_phone=profile.phone.strip(),
        contact_email=user.email,
        delivery_method=delivery_method,
        delivery_address=delivery_address,
        customer_note=customer_note,
        status=RentalOrder.Status.PENDING,
        deposit_status=RentalOrder.DepositStatus.UNCONFIRMED,
    )

    try:
        order.full_clean()
    except ValidationError as error:
        raise BookingConflict(
            "Thông tin đơn thuê không hợp lệ. "
            "Vui lòng kiểm tra và thử lại."
        ) from error

    order.save()

    _record_order_event(
        order=order,
        actor=user,
        title="Đã gửi yêu cầu thuê",
        message=(
            "Cửa hàng đã nhận yêu cầu thuê. "
            "Đơn đang chờ kiểm tra lịch và xác nhận tiền cọc."
        ),
    )

    return order


# CẬP NHẬT TRẠNG THÁI ĐƠN THUÊ
@transaction.atomic
def update_order_status(
    *,
    order_id,
    actor,
    new_status,
    customer_message="",
    condition_out=None,
    condition_in=None,
    return_method=None,
    staff_note=None,
):
    _check_order_permission(actor)

    order = get_order_for_update(order_id)

    if new_status not in RentalOrder.Status.values:
        raise ValidationError(
            "Trạng thái đơn thuê không hợp lệ."
        )

    if new_status == order.status:
        return order

    allowed = ALLOWED_TRANSITIONS.get(
        order.status,
        set(),
    )

    if new_status not in allowed:
        raise ValidationError(
            "Không thể chuyển đơn từ "
            f"'{order.get_status_display()}' "
            "sang trạng thái được yêu cầu."
        )

    customer_message = (
        customer_message or ""
    ).strip()

    if condition_out is not None:
        order.condition_out = condition_out.strip()

    if condition_in is not None:
        order.condition_in = condition_in.strip()

    if return_method is not None:
        order.return_method = return_method.strip()

    if staff_note is not None:
        order.staff_note = staff_note.strip()

    if new_status in {
        RentalOrder.Status.CONFIRMED,
        RentalOrder.Status.PREPARING,
        RentalOrder.Status.RENTED,
    }:
        camera = Camera.objects.select_for_update().get(
            pk=order.camera_id
        )

        if not has_capacity(
            camera,
            order.start_at,
            order.end_at,
            order.quantity,
            exclude_order_id=order.pk,
        ):
            raise BookingConflict(
                "Không đủ máy để xác nhận hoặc xử lý đơn. "
                "Vui lòng kiểm tra lịch thuê."
            )

    if new_status == RentalOrder.Status.CONFIRMED:
        if (
            order.deposit_amount is None
            or order.deposit_status
            == RentalOrder.DepositStatus.UNCONFIRMED
        ):
            raise ValidationError(
                "Cần xác nhận mức tiền cọc "
                "trước khi xác nhận đơn thuê."
            )

    if new_status == RentalOrder.Status.RENTED:
        if not order.condition_out.strip():
            raise ValidationError(
                "Vui lòng ghi nhận tình trạng máy trước khi giao."
            )

        if order.handover_at is None:
            order.handover_at = timezone.now()

    if new_status == RentalOrder.Status.RETURNED:
        if not order.condition_in.strip():
            raise ValidationError(
                "Vui lòng ghi nhận tình trạng máy khi nhận trả."
            )

        if not order.return_method.strip():
            raise ValidationError(
                "Vui lòng ghi nhận hình thức trả máy."
            )

        if order.returned_at is None:
            order.returned_at = timezone.now()

    if new_status == RentalOrder.Status.REJECTED:
        if not customer_message:
            raise ValidationError(
                "Vui lòng nhập lý do từ chối để thông báo cho khách hàng."
            )

    order.status = new_status
    order.full_clean()
    order.save()

    message = customer_message or (
        f"Đơn thuê đã chuyển sang trạng thái "
        f"{order.get_status_display().lower()}."
    )

    _record_order_event(
        order=order,
        actor=actor,
        title=f"Trạng thái đơn: {order.get_status_display()}",
        message=message,
    )

    return order


# CẬP NHẬT TIỀN CỌC
@transaction.atomic
def update_order_deposit(
    *,
    order_id,
    actor,
    new_status,
    amount=None,
    customer_message="",
):
    _check_order_permission(actor)

    order = get_order_for_update(order_id)

    if new_status not in RentalOrder.DepositStatus.values:
        raise ValidationError(
            "Trạng thái tiền cọc không hợp lệ."
        )

    old_status = order.deposit_status
    old_amount = order.deposit_amount

    if amount is None:
        amount = old_amount

    if amount is not None:
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
        ):
            raise ValidationError(
                "Số tiền cọc phải là số nguyên không âm."
            )

    if old_status in {
        RentalOrder.DepositStatus.RECEIVED,
        RentalOrder.DepositStatus.REFUNDED,
        RentalOrder.DepositStatus.DEDUCTED,
    } and amount != old_amount:
        raise ValidationError(
            "Không thể thay đổi mức tiền cọc "
            "sau khi đã nhận cọc."
        )

    if new_status != old_status:
        allowed = ALLOWED_DEPOSIT_TRANSITIONS.get(
            old_status,
            set(),
        )

        if new_status not in allowed:
            raise ValidationError(
                "Không thể chuyển trạng thái tiền cọc "
                "theo quy trình hiện tại."
            )

    if new_status != RentalOrder.DepositStatus.UNCONFIRMED:
        if amount is None or amount <= 0:
            raise ValidationError(
                "Vui lòng nhập mức tiền cọc hợp lệ."
            )

    if order.status in {
        RentalOrder.Status.REJECTED,
        RentalOrder.Status.CANCELLED,
        RentalOrder.Status.RETURNED,
    } and new_status in {
        RentalOrder.DepositStatus.DUE,
        RentalOrder.DepositStatus.RECEIVED,
    }:
        raise ValidationError(
            "Không thể yêu cầu hoặc nhận cọc "
            "cho đơn đã kết thúc."
        )

    customer_message = (
        customer_message or ""
    ).strip()

    if (
        new_status == RentalOrder.DepositStatus.DEDUCTED
        and not customer_message
    ):
        raise ValidationError(
            "Vui lòng nhập lý do khấu trừ tiền cọc."
        )

    if (
        new_status == old_status
        and amount == old_amount
    ):
        return order

    order.deposit_amount = amount
    order.deposit_status = new_status

    order.full_clean()
    order.save()

    message = customer_message or (
        f"Trạng thái tiền cọc đã được cập nhật: "
        f"{order.get_deposit_status_display().lower()}."
    )

    _record_order_event(
        order=order,
        actor=actor,
        title="Cập nhật tiền cọc",
        message=message,
    )

    return order


# KHÓA ĐƠN THUÊ KHI CẬP NHẬT
def get_order_for_update(order_id):
    try:
        return (
            RentalOrder.objects
            .select_for_update()
            .select_related("camera", "user")
            .get(pk=order_id)
        )
    except RentalOrder.DoesNotExist as error:
        raise ValidationError(
            "Không tìm thấy đơn thuê cần xử lý."
        ) from error

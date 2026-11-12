
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods, require_POST

from catalog.models import Camera, RentalRate

from .forms import RentalRequestForm
from .models import RentalOrder
from .services import (
    ALLOWED_DEPOSIT_TRANSITIONS,
    ALLOWED_TRANSITIONS,
    BookingConflict,
    create_order,
    has_capacity,
    update_order_deposit,
    update_order_status,
)


DRAFT_KEY = "rental_request"


# KHÁCH HÀNG CHỌN LỊCH THUÊ
@login_required
@require_http_methods(["GET", "POST"])
def booking(request, slug):
    camera = get_object_or_404(
        Camera,
        slug=slug,
        is_active=True,
    )

    profile = getattr(
        request.user,
        "customer_profile",
        None,
    )

    if not profile or not profile.phone.strip():
        messages.info(
            request,
            "Hãy cập nhật số điện thoại trong tài khoản "
            "trước khi đặt thuê.",
        )
        return redirect("customers:profile")

    if not camera.rates.filter(is_active=True).exists():
        messages.error(
            request,
            "Máy ảnh này chưa có gói thuê đang áp dụng.",
        )
        return redirect(camera.get_absolute_url())

    form = RentalRequestForm(
        request.POST or None,
        camera=camera,
    )

    if request.method == "POST" and form.is_valid():
        rate = form.cleaned_data["rate"]
        start_at = form.cleaned_data["start_at"]
        end_at = form.get_end_at()
        quantity = form.cleaned_data["quantity"]

        if not has_capacity(
            camera,
            start_at,
            end_at,
            quantity,
        ):
            form.add_error(
                None,
                "Máy hiện không còn đủ số lượng trong "
                "khoảng thời gian này. Vui lòng chọn lịch khác.",
            )

        else:
            request.session[DRAFT_KEY] = {
                "camera_id": camera.pk,
                "rate_id": rate.pk,
                "rate_amount": rate.amount,
                "rate_duration_hours": rate.duration_hours,
                "start_at": start_at.isoformat(),
                "quantity": quantity,
                "delivery_method": form.cleaned_data[
                    "delivery_method"
                ],
                "delivery_address": form.cleaned_data[
                    "delivery_address"
                ].strip(),
                "customer_note": form.cleaned_data[
                    "customer_note"
                ].strip(),
            }

            return redirect("rentals:review")

    return render(
        request,
        "rentals/booking.html",
        {
            "camera": camera,
            "form": form,
            "now_local": timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            ),
        },
    )


# KHÁCH HÀNG KIỂM TRA LẠI ĐƠN THUÊ
@login_required
@require_http_methods(["GET", "POST"])
def review(request):
    draft = request.session.get(DRAFT_KEY)

    if not isinstance(draft, dict):
        messages.info(
            request,
            "Hãy chọn máy và thời gian thuê trước.",
        )
        return redirect("catalog:list")

    try:
        camera_id = int(draft["camera_id"])
        rate_id = int(draft["rate_id"])
        start_at = datetime.fromisoformat(
            draft["start_at"]
        )
        quantity = int(draft["quantity"])

        delivery_method = draft["delivery_method"]
        delivery_address = draft["delivery_address"]
        customer_note = draft["customer_note"]

    except (KeyError, TypeError, ValueError):
        request.session.pop(DRAFT_KEY, None)

        messages.error(
            request,
            "Thông tin đặt thuê không hợp lệ. "
            "Vui lòng thực hiện lại.",
        )
        return redirect("catalog:list")

    camera = Camera.objects.filter(
        pk=camera_id,
        is_active=True,
    ).first()

    if camera is None:
        request.session.pop(DRAFT_KEY, None)

        messages.error(
            request,
            "Máy ảnh đã chọn hiện không còn kinh doanh.",
        )
        return redirect("catalog:list")

    rate = RentalRate.objects.filter(
        pk=rate_id,
        camera=camera,
        is_active=True,
    ).first()

    if rate is None:
        request.session.pop(DRAFT_KEY, None)

        messages.error(
            request,
            "Gói thuê đã chọn không còn áp dụng.",
        )
        return redirect(
            "rentals:booking",
            slug=camera.slug,
        )

    if timezone.is_naive(start_at):
        request.session.pop(DRAFT_KEY, None)

        messages.error(
            request,
            "Thời gian đặt thuê không hợp lệ.",
        )
        return redirect(
            "rentals:booking",
            slug=camera.slug,
        )

    if (
        draft.get("rate_amount", rate.amount) != rate.amount
        or draft.get(
            "rate_duration_hours",
            rate.duration_hours,
        ) != rate.duration_hours
    ):
        request.session.pop(DRAFT_KEY, None)

        messages.info(
            request,
            "Thông tin giá hoặc thời lượng thuê "
            "đã thay đổi. Vui lòng chọn lại gói thuê.",
        )
        return redirect(
            "rentals:booking",
            slug=camera.slug,
        )

    end_at = start_at + timedelta(
        hours=rate.duration_hours
    )

    total = rate.amount * quantity

    if request.method == "POST":
        if request.POST.get("confirm") != "yes":
            messages.error(
                request,
                "Vui lòng xác nhận lại thông tin thuê.",
            )
            return redirect("rentals:review")

        if start_at <= timezone.now():
            request.session.pop(DRAFT_KEY, None)

            messages.error(
                request,
                "Thời gian nhận máy đã qua. "
                "Vui lòng chọn lịch mới.",
            )
            return redirect(
                "rentals:booking",
                slug=camera.slug,
            )

        try:
            order = create_order(
                user=request.user,
                camera=camera,
                rate=rate,
                form_data={
                    "start_at": start_at,
                    "quantity": quantity,
                    "delivery_method": delivery_method,
                    "delivery_address": delivery_address,
                    "customer_note": customer_note,
                },
            )

        except BookingConflict as error:
            messages.error(
                request,
                str(error),
            )
            return redirect(
                "rentals:booking",
                slug=camera.slug,
            )

        request.session.pop(DRAFT_KEY, None)

        messages.success(
            request,
            "Yêu cầu thuê đã được gửi thành công.",
        )

        return redirect(
            "rentals:success",
            pk=order.pk,
        )

    return render(
        request,
        "rentals/review.html",
        {
            "camera": camera,
            "rate": rate,
            "start_at": start_at,
            "end_at": end_at,
            "quantity": quantity,
            "delivery_method": delivery_method,
            "delivery_address": delivery_address,
            "customer_note": customer_note,
            "total": total,
        },
    )


# TRANG GỬI ĐƠN THÀNH CÔNG
@login_required
def success(request, pk):
    order = get_object_or_404(
        RentalOrder.objects.select_related(
            "camera",
            "rate",
        ),
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "rentals/success.html",
        {
            "order": order,
        },
    )


# DANH SÁCH ĐƠN THUÊ CỦA KHÁCH HÀNG
@login_required
def order_list(request):
    orders = RentalOrder.objects.filter(
        user=request.user
    ).select_related(
        "camera",
        "rate",
    ).order_by("-created_at")

    return render(
        request,
        "rentals/order_list.html",
        {
            "orders": orders,
        },
    )


# CHI TIẾT ĐƠN THUÊ CỦA KHÁCH HÀNG
@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        RentalOrder.objects.select_related(
            "camera",
            "rate",
        ).prefetch_related("events"),
        pk=pk,
        user=request.user,
    )

    order.staff_note = ""

    return render(
        request,
        "rentals/order_detail.html",
        {
            "order": order,
        },
    )


# NHÂN VIÊN XEM DANH SÁCH ĐƠN THUÊ
@staff_member_required(login_url="customers:login")
@permission_required(
    "rentals.view_rentalorder",
    raise_exception=True,
)
def staff_order_list(request):
    orders = RentalOrder.objects.select_related(
        "user",
        "camera",
        "rate",
    )

    query = request.GET.get(
        "q",
        "",
    ).strip()[:100]

    status_filter = request.GET.get(
        "status",
        "all",
    )

    deposit_filter = request.GET.get(
        "deposit",
        "all",
    )

    date_from = request.GET.get(
        "date_from",
        "",
    )

    date_to = request.GET.get(
        "date_to",
        "",
    )

    if query:
        orders = orders.filter(
            Q(order_code__icontains=query)
            | Q(contact_name__icontains=query)
            | Q(contact_phone__icontains=query)
            | Q(user__email__icontains=query)
            | Q(camera__name__icontains=query)
        )

    valid_statuses = set(
        RentalOrder.Status.values
    )

    if status_filter in valid_statuses:
        orders = orders.filter(
            status=status_filter
        )

    valid_deposit_statuses = set(
        RentalOrder.DepositStatus.values
    )

    if deposit_filter in valid_deposit_statuses:
        orders = orders.filter(
            deposit_status=deposit_filter
        )

    parsed_from = parse_date(date_from)
    parsed_to = parse_date(date_to)

    if parsed_from:
        orders = orders.filter(
            start_at__date__gte=parsed_from
        )

    if parsed_to:
        orders = orders.filter(
            start_at__date__lte=parsed_to
        )

    now = timezone.now()

    statistics = RentalOrder.objects.aggregate(
        total=Count("id"),
        pending=Count(
            "id",
            filter=Q(
                status=RentalOrder.Status.PENDING
            ),
        ),
        active=Count(
            "id",
            filter=Q(
                status__in=[
                    RentalOrder.Status.CONFIRMED,
                    RentalOrder.Status.PREPARING,
                    RentalOrder.Status.RENTED,
                ]
            ),
        ),
        overdue=Count(
            "id",
            filter=Q(
                status=RentalOrder.Status.RENTED,
                returned_at__isnull=True,
                end_at__lt=now,
            ),
        ),
    )

    paginator = Paginator(
        orders.order_by("-created_at"),
        12,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "rentals/staff_order_list.html",
        {
            "orders": page_obj,
            "page_obj": page_obj,
            "statistics": statistics,
            "query": query,
            "status_filter": status_filter,
            "deposit_filter": deposit_filter,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": RentalOrder.Status.choices,
            "deposit_choices": RentalOrder.DepositStatus.choices,
        },
    )


# NHÂN VIÊN XEM CHI TIẾT ĐƠN THUÊ
@staff_member_required(login_url="customers:login")
@permission_required(
    "rentals.view_rentalorder",
    raise_exception=True,
)
def staff_order_detail(request, pk):
    order = get_object_or_404(
        RentalOrder.objects.select_related(
            "user",
            "camera",
            "rate",
        ).prefetch_related("events"),
        pk=pk,
    )

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        order.status,
        set(),
    )

    allowed_deposit_statuses = (
        ALLOWED_DEPOSIT_TRANSITIONS.get(
            order.deposit_status,
            set(),
        )
    )

    status_choices = [
        (value, label)
        for value, label in RentalOrder.Status.choices
        if value in allowed_statuses
    ]

    deposit_choices = [
        (value, label)
        for value, label in RentalOrder.DepositStatus.choices
        if value in allowed_deposit_statuses
    ]

    can_change = request.user.has_perm(
        "rentals.change_rentalorder"
    )

    return render(
        request,
        "rentals/staff_order_detail.html",
        {
            "order": order,
            "status_choices": status_choices,
            "deposit_choices": deposit_choices,
            "can_change": can_change,
            "is_overdue": order.is_overdue,
        },
    )


# NHÂN VIÊN CẬP NHẬT TRẠNG THÁI ĐƠN
@staff_member_required(login_url="customers:login")
@permission_required(
    "rentals.change_rentalorder",
    raise_exception=True,
)
@require_POST
def staff_order_status(request, pk):
    new_status = request.POST.get(
        "status",
        "",
    ).strip()

    customer_message = request.POST.get(
        "customer_message",
        "",
    ).strip()

    optional_fields = {}

    for field in (
        "condition_out",
        "condition_in",
        "return_method",
        "staff_note",
    ):
        if field in request.POST:
            optional_fields[field] = request.POST.get(
                field,
                "",
            )

    try:
        order = update_order_status(
            order_id=pk,
            actor=request.user,
            new_status=new_status,
            customer_message=customer_message,
            **optional_fields,
        )

    except (BookingConflict, ValidationError) as error:
        if isinstance(error, ValidationError):
            error_message = " ".join(error.messages)
        else:
            error_message = str(error)

        messages.error(
            request,
            error_message,
        )

    else:
        messages.success(
            request,
            f"Đã cập nhật đơn {order.order_code} "
            f"sang trạng thái {order.get_status_display()}.",
        )

    return redirect(
        "rentals:staff_order_detail",
        pk=pk,
    )


# NHÂN VIÊN CẬP NHẬT TIỀN CỌC
@staff_member_required(login_url="customers:login")
@permission_required(
    "rentals.change_rentalorder",
    raise_exception=True,
)
@require_POST
def staff_order_deposit(request, pk):
    new_status = request.POST.get(
        "deposit_status",
        "",
    ).strip()

    raw_amount = request.POST.get(
        "deposit_amount",
        "",
    ).strip()

    customer_message = request.POST.get(
        "customer_message",
        "",
    ).strip()

    if raw_amount:
        try:
            amount = int(raw_amount)
        except ValueError:
            messages.error(
                request,
                "Tiền cọc phải là số nguyên hợp lệ.",
            )

            return redirect(
                "rentals:staff_order_detail",
                pk=pk,
            )
    else:
        amount = None

    try:
        order = update_order_deposit(
            order_id=pk,
            actor=request.user,
            new_status=new_status,
            amount=amount,
            customer_message=customer_message,
        )

    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )

    else:
        messages.success(
            request,
            f"Đã cập nhật tiền cọc của đơn "
            f"{order.order_code}.",
        )

    return redirect(
        "rentals:staff_order_detail",
        pk=pk,
    )

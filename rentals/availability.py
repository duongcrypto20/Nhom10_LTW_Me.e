
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Camera
from .models import RentalOrder
from .services import has_capacity


# KIỂM TRA LỊCH MÁY TRỐNG
@staff_member_required(login_url="customers:login")
@permission_required("rentals.view_rentalorder", raise_exception=True)
def staff_availability(request):
    cameras = Camera.objects.filter(
        is_active=True
    ).order_by("brand", "name")

    selected = {
        "camera": request.GET.get("camera", ""),
        "start_at": request.GET.get("start_at", ""),
        "hours": request.GET.get("hours", "23"),
        "quantity": request.GET.get("quantity", "1"),
    }

    camera = None
    result = None

    if "camera" in request.GET:
        try:
            camera = cameras.get(
                pk=int(selected["camera"])
            )

            naive_start = datetime.strptime(
                selected["start_at"],
                "%Y-%m-%dT%H:%M",
            )

            start_at = timezone.make_aware(
                naive_start,
                timezone.get_current_timezone(),
            )

            hours = int(selected["hours"])
            quantity = int(selected["quantity"])

            if not 1 <= hours <= 720:
                raise ValueError

            if not 1 <= quantity <= 10:
                raise ValueError

            if start_at <= timezone.now():
                raise ValueError

            end_at = start_at + timedelta(hours=hours)

            result = {
                "available": has_capacity(
                    camera,
                    start_at,
                    end_at,
                    quantity,
                ),
                "start_at": start_at,
                "end_at": end_at,
                "quantity": quantity,
                "total_units": camera.available_units,
                "orders": RentalOrder.objects.filter(
                    camera=camera,
                    status__in=[
                        RentalOrder.Status.PENDING,
                        RentalOrder.Status.CONFIRMED,
                        RentalOrder.Status.PREPARING,
                        RentalOrder.Status.RENTED,
                    ],
                    start_at__lt=end_at,
                ).order_by("start_at")[:30],
            }

        except (Camera.DoesNotExist, ValueError, OverflowError):
            messages.error(
                request,
                "Thông tin kiểm tra lịch không hợp lệ. "
                "Vui lòng chọn máy, thời gian và số lượng hợp lệ.",
            )

    return render(
        request,
        "rentals/staff_availability.html",
        {
            "cameras": cameras,
            "selected": selected,
            "camera": camera,
            "result": result,
        },
    )

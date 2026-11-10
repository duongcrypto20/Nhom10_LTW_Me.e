from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from catalog.models import Camera, RentalRate
from .forms import RentalRequestForm
from .models import RentalOrder
from .services import BookingConflict, create_order, has_capacity

DRAFT_KEY = "rental_request"


@login_required
def booking(request, slug):
    camera = get_object_or_404(Camera, slug=slug, is_active=True)
    profile = getattr(request.user, "customer_profile", None)
    if not profile or not profile.phone.strip():
        messages.info(request, "Hãy cập nhật số điện thoại trong tài khoản trước khi đặt thuê.")
        return redirect("customers:profile")
    if not camera.rates.filter(is_active=True).exists():
        messages.error(request, "Máy ảnh này chưa có gói thuê đang áp dụng.")
        return redirect(camera.get_absolute_url())

    form = RentalRequestForm(
        request.POST or None,
        camera=camera,
    )
    if request.method == "POST" and form.is_valid():
        rate = form.cleaned_data["rate"]
        end_at = form.get_end_at()
        if not has_capacity(
            camera,
            form.cleaned_data["start_at"],
            end_at,
            form.cleaned_data["quantity"],
        ):
            form.add_error(
                None,
                "Máy hiện không còn đủ số lượng trong khoảng thời gian này. "
                "Vui lòng chọn lịch khác.",
            )
        else:
            request.session[DRAFT_KEY] = {
                "camera_id": camera.pk,
                "rate_id": rate.pk,
                "start_at": form.cleaned_data["start_at"].isoformat(),
                "end_at": end_at.isoformat(),
                "quantity": form.cleaned_data["quantity"],
                "delivery_method": form.cleaned_data["delivery_method"],
                "delivery_address": form.cleaned_data["delivery_address"].strip(),
                "customer_note": form.cleaned_data["customer_note"].strip(),
            }
            return redirect("rentals:review")

    return render(
        request,
        "rentals/booking.html",
        {
            "camera": camera,
            "form": form,
            "now_local": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        },
    )


@login_required
def review(request):
    draft = request.session.get(DRAFT_KEY)
    if not draft:
        messages.info(request, "Hãy chọn máy và thời gian thuê trước.")
        return redirect("catalog:list")

    camera = get_object_or_404(Camera, pk=draft["camera_id"], is_active=True)
    rate = get_object_or_404(
        RentalRate,
        pk=draft["rate_id"],
        camera=camera,
        is_active=True,
    )
    start_at = datetime.fromisoformat(draft["start_at"])
    end_at = datetime.fromisoformat(draft["end_at"])
    total = rate.amount * draft["quantity"]

    if request.method == "POST":
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Vui lòng xác nhận lại thông tin thuê.")
            return redirect("rentals:booking", slug=camera.slug)
        if start_at <= timezone.now():
            del request.session[DRAFT_KEY]
            messages.error(request, "Thời gian nhận máy đã qua. Hãy chọn lịch mới.")
            return redirect("rentals:booking", slug=camera.slug)
        try:
            order = create_order(
                user=request.user,
                camera=camera,
                rate=rate,
                form_data={
                    "start_at": start_at,
                    "quantity": draft["quantity"],
                    "delivery_method": draft["delivery_method"],
                    "delivery_address": draft["delivery_address"],
                    "customer_note": draft["customer_note"],
                },
            )
        except BookingConflict as error:
            messages.error(request, str(error))
            return redirect("rentals:booking", slug=camera.slug)
        del request.session[DRAFT_KEY]
        return redirect("rentals:success", pk=order.pk)

    return render(
        request,
        "rentals/review.html",
        {
            "camera": camera,
            "rate": rate,
            "start_at": start_at,
            "end_at": end_at,
            "quantity": draft["quantity"],
            "delivery_method": draft["delivery_method"],
            "delivery_address": draft["delivery_address"],
            "customer_note": draft["customer_note"],
            "total": total,
        },
    )


@login_required
def success(request, pk):
    order = get_object_or_404(
        RentalOrder.objects.select_related("camera", "rate"),
        pk=pk,
        user=request.user,
    )
    return render(request, "rentals/success.html", {"order": order})


@login_required
def order_list(request):
    orders = RentalOrder.objects.filter(user=request.user).select_related(
        "camera", "rate"
    )
    return render(request, "rentals/order_list.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        RentalOrder.objects.select_related("camera", "rate").prefetch_related("events"),
        pk=pk,
        user=request.user,
    )
    return render(request, "rentals/order_detail.html", {"order": order})

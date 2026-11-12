
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from customers.models import CustomerProfile
from .models import Camera, RentalRate
from .staff_forms import CameraManageForm, RentalRateManageForm


# KIỂM TRA VAI TRÒ CHỦ CỬA HÀNG
def _manager_only(user):
    profile = getattr(user, "customer_profile", None)

    if not (
        user.is_superuser
        or (
            profile
            and profile.role == CustomerProfile.Role.MANAGER
        )
    ):
        raise PermissionDenied(
            "Chỉ chủ cửa hàng có quyền thêm máy hoặc gói thuê."
        )


# DANH SÁCH QUẢN LÝ MÁY ẢNH
@staff_member_required(login_url="customers:login")
@permission_required("catalog.view_camera", raise_exception=True)
def manage_cameras(request):
    q = request.GET.get("q", "").strip()[:100]

    cameras = Camera.objects.all()

    if q:
        cameras = cameras.filter(
            Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(slug__icontains=q)
        )

    profile = getattr(request.user, "customer_profile", None)
    can_add = request.user.has_perm("catalog.add_camera") and (
        request.user.is_superuser
        or (
            profile
            and profile.role == CustomerProfile.Role.MANAGER
        )
    )

    return render(
        request,
        "catalog/staff_cameras.html",
        {
            "cameras": cameras.order_by("brand", "name"),
            "q": q,
            "can_add": can_add,
        },
    )


# CHỦ CỬA HÀNG THÊM MÁY
@staff_member_required(login_url="customers:login")
@permission_required("catalog.add_camera", raise_exception=True)
@require_http_methods(["GET", "POST"])
def create_camera(request):
    _manager_only(request.user)

    form = CameraManageForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm máy ảnh.")
        return redirect("catalog:manage_cameras")

    return render(
        request,
        "catalog/staff_form.html",
        {
            "form": form,
            "heading": "Thêm máy ảnh",
            "back": "catalog:manage_cameras",
        },
    )


# CẬP NHẬT MÁY ẢNH
@staff_member_required(login_url="customers:login")
@permission_required("catalog.change_camera", raise_exception=True)
@require_http_methods(["GET", "POST"])
def edit_camera(request, pk):
    camera = get_object_or_404(Camera, pk=pk)

    form = CameraManageForm(
        request.POST or None,
        instance=camera,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Thông tin máy ảnh đã được cập nhật.",
        )
        return redirect("catalog:manage_cameras")

    return render(
        request,
        "catalog/staff_form.html",
        {
            "form": form,
            "heading": f"Cập nhật {camera.name}",
            "back": "catalog:manage_cameras",
        },
    )


# DANH SÁCH GÓI THUÊ VÀ GIÁ
@staff_member_required(login_url="customers:login")
@permission_required("catalog.view_rentalrate", raise_exception=True)
def manage_rates(request):
    q = request.GET.get("q", "").strip()[:100]

    rates = RentalRate.objects.select_related("camera")

    if q:
        rates = rates.filter(
            Q(camera__name__icontains=q)
            | Q(label__icontains=q)
        )

    profile = getattr(request.user, "customer_profile", None)
    can_add = request.user.has_perm("catalog.add_rentalrate") and (
        request.user.is_superuser
        or (
            profile
            and profile.role == CustomerProfile.Role.MANAGER
        )
    )

    return render(
        request,
        "catalog/staff_rates.html",
        {
            "rates": rates.order_by(
                "camera__name",
                "sort_order",
            ),
            "q": q,
            "can_add": can_add,
        },
    )


# CHỦ CỬA HÀNG THÊM GÓI THUÊ
@staff_member_required(login_url="customers:login")
@permission_required("catalog.add_rentalrate", raise_exception=True)
@require_http_methods(["GET", "POST"])
def create_rate(request):
    _manager_only(request.user)

    form = RentalRateManageForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã thêm gói thuê.")
        return redirect("catalog:manage_rates")

    return render(
        request,
        "catalog/staff_form.html",
        {
            "form": form,
            "heading": "Thêm gói thuê",
            "back": "catalog:manage_rates",
        },
    )


# CẬP NHẬT GÓI THUÊ VÀ GIÁ
@staff_member_required(login_url="customers:login")
@permission_required("catalog.change_rentalrate", raise_exception=True)
@require_http_methods(["GET", "POST"])
def edit_rate(request, pk):
    rate = get_object_or_404(RentalRate, pk=pk)

    form = RentalRateManageForm(
        request.POST or None,
        instance=rate,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Đã cập nhật gói thuê và giá thuê.",
        )
        return redirect("catalog:manage_rates")

    return render(
        request,
        "catalog/staff_form.html",
        {
            "form": form,
            "heading": f"Cập nhật {rate}",
            "back": "catalog:manage_rates",
        },
    )

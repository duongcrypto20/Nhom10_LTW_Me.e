
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import CustomerProfile

User = get_user_model()


# BIỂU MẪU CẬP NHẬT TÀI KHOẢN
class StaffAccountForm(forms.Form):
    first_name = forms.CharField(
        label="Họ và tên",
        max_length=150,
    )

    phone = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
    )

    role = forms.ChoiceField(
        label="Vai trò",
        choices=[
            (CustomerProfile.Role.CUSTOMER, "Khách hàng"),
            (CustomerProfile.Role.STAFF, "Nhân viên"),
        ],
    )

    is_active = forms.BooleanField(
        label="Cho phép đăng nhập",
        required=False,
    )


# KIỂM TRA QUYỀN CHỦ CỬA HÀNG
def ensure_manager(user):
    role = getattr(
        getattr(user, "customer_profile", None),
        "role",
        None,
    )

    if not (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and (
            user.is_superuser
            or role == CustomerProfile.Role.MANAGER
        )
    ):
        raise PermissionDenied(
            "Chỉ chủ cửa hàng được quản lý tài khoản."
        )


# DANH SÁCH TÀI KHOẢN
@staff_member_required(login_url="customers:login")
def staff_accounts(request):
    ensure_manager(request.user)

    query = request.GET.get("q", "").strip()[:100]

    users = User.objects.select_related(
        "customer_profile"
    ).order_by("-date_joined")

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
        )

    return render(
        request,
        "customers/staff_accounts.html",
        {
            "users": users,
            "query": query,
        },
    )


# CHỈNH SỬA VÀ PHÂN QUYỀN
@staff_member_required(login_url="customers:login")
@require_http_methods(["GET", "POST"])
def staff_account_edit(request, pk):
    ensure_manager(request.user)

    target = get_object_or_404(User, pk=pk)

    profile, _ = CustomerProfile.objects.get_or_create(
        user=target
    )

    if (
        target.is_superuser
        or target.pk == request.user.pk
        or profile.role == CustomerProfile.Role.MANAGER
    ):
        raise PermissionDenied(
            "Không thể chỉnh sửa tài khoản quản trị "
            "cấp cao tại màn hình này."
        )

    form = StaffAccountForm(
        request.POST or None,
        initial={
            "first_name": target.first_name,
            "phone": profile.phone,
            "role": profile.role,
            "is_active": target.is_active,
        },
    )

    if request.method == "POST" and form.is_valid():
        target.first_name = form.cleaned_data[
            "first_name"
        ].strip()

        target.is_active = form.cleaned_data["is_active"]

        target.save(
            update_fields=["first_name", "is_active"]
        )

        profile.phone = form.cleaned_data["phone"].strip()
        profile.role = form.cleaned_data["role"]
        profile.save()

        messages.success(
            request,
            "Đã cập nhật thông tin và phân quyền tài khoản.",
        )

        return redirect("customers:staff_accounts")

    return render(
        request,
        "customers/staff_account_edit.html",
        {
            "form": form,
            "target": target,
        },
    )

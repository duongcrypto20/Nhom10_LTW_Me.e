from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Camera
from feedback.models import Feedback
from rentals.models import RentalOrder
from .forms import AccountForm, AddressForm, RegisterForm
from .models import Address, CustomerProfile, Notification

User = get_user_model()


@staff_member_required
def staff_dashboard(request):
    profile = getattr(request.user, "customer_profile", None)
    status_counts = dict(
        RentalOrder.objects.values("status")
        .annotate(total=Count("id"))
        .values_list("status", "total")
    )
    status_cards = [
        {"label": label, "total": status_counts.get(value, 0)}
        for value, label in RentalOrder.Status.choices
    ]
    feedback_summary = Feedback.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(is_published=False)),
        average=Avg("rating", filter=Q(is_published=True)),
    )
    return render(
        request,
        "customers/staff_dashboard.html",
        {
            "profile": profile,
            "is_manager": bool(
                request.user.is_superuser
                or profile and profile.role == CustomerProfile.Role.MANAGER
            ),
            "camera_count": Camera.objects.filter(is_active=True).count(),
            "customer_count": User.objects.filter(is_staff=False, is_superuser=False).count(),
            "status_cards": status_cards,
            "feedback_summary": feedback_summary,
            "recent_orders": RentalOrder.objects.select_related("user", "camera")[:8],
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("customers:profile")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Tài khoản đã được tạo.")
        return redirect("customers:profile")
    return render(request, "customers/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("customers:profile")
    form = AuthenticationForm(request, data=request.POST or None)
    form.fields["username"].label = "Email"
    form.fields["username"].widget.attrs["autocomplete"] = "email"
    form.fields["password"].label = "Mật khẩu"
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["username"].strip().lower()
        user = authenticate(
            request,
            username=email,
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("customers:profile")
    return render(request, "customers/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Bạn đã đăng xuất.")
    return redirect("catalog:home")


@login_required
def profile(request):
    default_role = CustomerProfile.Role.CUSTOMER
    if request.user.is_superuser:
        default_role = CustomerProfile.Role.MANAGER
    elif request.user.is_staff:
        default_role = CustomerProfile.Role.STAFF
    user_profile, _ = CustomerProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": default_role},
    )
    form = AccountForm(
        request.POST or None,
        initial={
            "first_name": request.user.get_full_name() or request.user.first_name,
            "phone": user_profile.phone,
        },
    )
    if request.method == "POST" and form.is_valid():
        request.user.first_name = form.cleaned_data["first_name"].strip()
        user_profile.phone = form.cleaned_data["phone"].strip()
        request.user.save(update_fields=["first_name"])
        user_profile.save(update_fields=["phone"])
        messages.success(request, "Thông tin tài khoản đã được cập nhật.")
        return redirect("customers:profile")

    orders = RentalOrder.objects.filter(user=request.user).select_related(
        "camera", "rate"
    )[:5]
    return render(
        request,
        "customers/profile.html",
        {
            "form": form,
            "profile": user_profile,
            "orders": orders,
            "unread_count": request.user.notifications.filter(read_at__isnull=True).count(),
        },
    )


@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(
        request,
        "customers/addresses.html",
        {"addresses": addresses, "form": AddressForm()},
    )


@login_required
def address_create(request):
    if request.method != "POST":
        return redirect("customers:addresses")
    form = AddressForm(request.POST)
    if form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, "Địa chỉ đã được lưu.")
    else:
        return render(
            request,
            "customers/addresses.html",
            {
                "addresses": Address.objects.filter(user=request.user),
                "form": form,
            },
            status=400,
        )
    return redirect("customers:addresses")


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Địa chỉ đã được xóa.")
    return redirect("customers:addresses")


@login_required
@require_POST
def address_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save(update_fields=["is_default"])
    messages.success(request, "Địa chỉ mặc định đã được cập nhật.")
    return redirect("customers:addresses")


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(
        request,
        "customers/notifications.html",
        {"notifications": notifications},
    )


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        user=request.user,
    )
    notification.mark_read()
    if notification.order_id:
        return redirect("rentals:detail", pk=notification.order_id)
    return redirect("customers:notifications")

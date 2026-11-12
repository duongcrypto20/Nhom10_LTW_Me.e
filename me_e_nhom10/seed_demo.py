import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile, Notification
from feedback.models import Feedback
from rentals.models import RentalEvent, RentalOrder

User = get_user_model()


def make_account(email, name, phone, role=CustomerProfile.Role.CUSTOMER):
    user = User.objects.filter(username=email).first()
    if user:
        if user.email.lower() != email.lower():
            raise ValueError(f"Tên đăng nhập {email} đã thuộc tài khoản khác.")
        created = False
    else:
        password = secrets.token_urlsafe(12)
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=name,
            password=password,
        )
        created = True
        print(f"TÀI KHOẢN MỚI: {email} | Mật khẩu: {password}")

    profile, profile_created = CustomerProfile.objects.get_or_create(
        user=user,
        defaults={"phone": phone, "role": role},
    )
    if not created and not profile_created:
        print(f"Đã có tài khoản {email}, giữ nguyên mật khẩu và vai trò.")
    return user


def slot(day_offset):
    return timezone.localtime(timezone.now() + timedelta(days=day_offset)).replace(
        hour=9, minute=0, second=0, microsecond=0,
    )


def seed():
    cameras = list(Camera.objects.filter(is_active=True).order_by("pk")[:10])
    if len(cameras) < 10:
        raise RuntimeError("Cần ít nhất 10 máy ảnh đang kinh doanh để tạo dữ liệu này.")

    rates = []
    for camera in cameras:
        rate = RentalRate.objects.filter(
            camera=camera, duration_hours=23, is_active=True,
        ).first()
        if rate is None:
            raise RuntimeError(f"{camera.name} chưa có gói 1 ngày (23 giờ) đang áp dụng.")
        rates.append(rate)

    with transaction.atomic():
        customers = [
            make_account("mee.khach01@example.com", "Nguyễn Minh Anh", "0900000001"),
            make_account("mee.khach02@example.com", "Trần Bảo Ngọc", "0900000002"),
            make_account("mee.khach03@example.com", "Lê Gia Huy", "0900000003"),
        ]
        staff = make_account(
            "mee.nhanvien@example.com", "Nhân viên mẫu", "0900000004",
            CustomerProfile.Role.STAFF,
        )

        P = RentalOrder.Status
        D = RentalOrder.DepositStatus
        cases = [
            ("MEE-DEMO-01", 0, 0, P.PENDING, 2, D.UNCONFIRMED, None),
            ("MEE-DEMO-02", 1, 1, P.CONFIRMED, 4, D.DUE, 300000),
            ("MEE-DEMO-03", 2, 2, P.PREPARING, 6, D.RECEIVED, 300000),
            ("MEE-DEMO-04", 0, 3, P.RENTED, -1, D.RECEIVED, 300000),
            ("MEE-DEMO-05", 1, 4, P.RENTED, -4, D.RECEIVED, 300000),
            ("MEE-DEMO-06", 0, 5, P.RETURNED, -10, D.REFUNDED, 300000),
            ("MEE-DEMO-07", 1, 6, P.RETURNED, -8, D.REFUNDED, 300000),
            ("MEE-DEMO-08", 2, 7, P.RETURNED, -6, D.DEDUCTED, 300000),
            ("MEE-DEMO-09", 0, 8, P.REJECTED, 8, D.UNCONFIRMED, None),
            ("MEE-DEMO-10", 1, 9, P.CANCELLED, 10, D.UNCONFIRMED, None),
        ]

        for code, customer_idx, camera_idx, status, days, deposit_status, deposit in cases:
            if RentalOrder.objects.filter(order_code=code).exists():
                print(f"Giữ nguyên đơn đã có: {code}")
                continue

            user = customers[customer_idx]
            camera = cameras[camera_idx]
            rate = rates[camera_idx]
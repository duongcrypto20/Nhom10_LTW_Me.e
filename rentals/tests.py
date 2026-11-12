
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile, Notification

from .admin import RentalOrderAdminForm
from .models import RentalEvent, RentalOrder
from .services import (
    has_capacity,
    update_order_deposit,
    update_order_status,
)

User = get_user_model()


# DỮ LIỆU KIỂM THỬ
class RentalTestData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="customer@example.test",
            email="customer@example.test",
            first_name="Khách hàng",
            password="Secure-test-Password-123!",
        )
        CustomerProfile.objects.create(
            user=cls.customer,
            phone="0900000000",
        )

        cls.other_customer = User.objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="Secure-test-Password-123!",
        )
        CustomerProfile.objects.create(
            user=cls.other_customer,
            phone="0900000001",
        )

        cls.manager = User.objects.create_superuser(
            username="manager@example.test",
            email="manager@example.test",
            password="Secure-test-Password-123!",
        )

        cls.viewer = User.objects.create_user(
            username="viewer@example.test",
            email="viewer@example.test",
            password="Secure-test-Password-123!",
            is_staff=True,
        )
        cls.viewer.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="rentals",
                codename="view_rentalorder",
            )
        )

        cls.camera = Camera.objects.create(
            name="Canon M10",
            slug="canon-m10",
            brand=Camera.Brand.CANON,
            image="images/products/canonm10.jpg",
            available_units=1,
        )
        cls.rate = RentalRate.objects.create(
            camera=cls.camera,
            label="1 ngày",
            duration_hours=23,
            amount=130000,
        )
        cls.short_rate = RentalRate.objects.create(
            camera=cls.camera,
            label="6 giờ",
            duration_hours=6,
            amount=90000,
        )

    def form_data(self, start_at=None, rate=None, **changes):
        if start_at is None:
            start_at = timezone.localtime(
                timezone.now() + timedelta(days=2)
            ).replace(hour=10, minute=0, second=0, microsecond=0)

        data = {
            "rate": str((rate or self.rate).pk),
            "start_at": timezone.localtime(start_at).strftime("%Y-%m-%dT%H:%M"),
            "quantity": "1",
            "delivery_method": RentalOrder.DeliveryMethod.PICKUP,
            "delivery_address": "",
            "customer_note": "",
            "accept_policy": "on",
        }
        data.update(changes)
        return data

    def make_order(self, **changes):
        start_at = changes.pop(
            "start_at",
            timezone.now() + timedelta(days=3),
        )
        end_at = changes.pop(
            "end_at",
            start_at + timedelta(hours=23),
        )
        data = {
            "user": self.customer,
            "camera": self.camera,
            "rate": self.rate,
            "start_at": start_at,
            "end_at": end_at,
            "quantity": 1,
            "rate_label": self.rate.label,
            "duration_hours": self.rate.duration_hours,
            "rental_total": self.rate.amount,
            "contact_name": "Khách hàng",
            "contact_phone": "0900000000",
            "contact_email": "customer@example.test",
            "delivery_method": RentalOrder.DeliveryMethod.PICKUP,
        }
        data.update(changes)
        return RentalOrder.objects.create(**data)


# ĐẶT THUÊ VÀ TRA CỨU ĐƠN CỦA KHÁCH
class RentalCustomerTests(RentalTestData):
    def setUp(self):
        self.client.force_login(self.customer)

    def test_booking_creates_pending_order_and_notification(self):
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.form_data(),
        )
        self.assertRedirects(response, reverse("rentals:review"))

        response = self.client.post(
            reverse("rentals:review"),
            {"confirm": "yes"},
        )
        order = RentalOrder.objects.get(user=self.customer)
        self.assertRedirects(
            response,
            reverse("rentals:success", args=[order.pk]),
        )
        self.assertEqual(order.status, RentalOrder.Status.PENDING)
        self.assertEqual(order.rental_total, 130000)
        self.assertEqual(order.end_at - order.start_at, timedelta(hours=23))
        self.assertTrue(RentalEvent.objects.filter(order=order).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                order_id=order.pk,
            ).exists()
        )

    def test_cannot_book_overlapping_pending_order(self):
        data = self.form_data()
        naive_start = datetime.strptime(
            data["start_at"],
            "%Y-%m-%dT%H:%M",
        )
        start_at = timezone.make_aware(naive_start)
        self.make_order(start_at=start_at)

        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "không còn đủ số lượng")
        self.assertEqual(RentalOrder.objects.count(), 1)

    def test_six_hour_rate_requires_eight_or_fifteen_oclock(self):
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.form_data(rate=self.short_rate),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "08:00 hoặc 15:00")
        self.assertEqual(RentalOrder.objects.count(), 0)

    def test_delivery_requires_address(self):
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.form_data(
                delivery_method=RentalOrder.DeliveryMethod.DELIVERY
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vui lòng nhập địa chỉ giao nhận")
        self.assertEqual(RentalOrder.objects.count(), 0)

    def test_guest_must_sign_in_before_booking(self):
        self.client.logout()
        path = reverse("rentals:booking", args=[self.camera.slug])
        response = self.client.get(path)
        self.assertRedirects(
            response,
            f"{reverse('customers:login')}?next={path}",
        )

    def test_pickup_is_default_delivery_method(self):
        response = self.client.get(
            reverse("rentals:booking", args=[self.camera.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["delivery_method"].value(),
            RentalOrder.DeliveryMethod.PICKUP,
        )

    def test_guest_cannot_view_customer_order(self):
        order = self.make_order()
        self.client.logout()
        response = self.client.get(
            reverse("rentals:detail", args=[order.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_view_another_customers_order(self):
        order = self.make_order(user=self.other_customer)
        response = self.client.get(
            reverse("rentals:detail", args=[order.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_cannot_view_another_customers_success_page(self):
        order = self.make_order(user=self.other_customer)
        response = self.client.get(
            reverse("rentals:success", args=[order.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_order_detail_does_not_expose_private_notes(self):
        order = self.make_order(
            staff_note="GHI CHÚ NỘI BỘ BẢO MẬT"
        )
        RentalEvent.objects.create(
            order=order,
            actor=self.manager,
            title="Cập nhật thông tin nội bộ",
            details="NỘI DUNG NỘI BỘ KHÔNG CÔNG KHAI",
        )
        response = self.client.get(
            reverse("rentals:detail", args=[order.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            "GHI CHÚ NỘI BỘ BẢO MẬT",
        )
        self.assertNotContains(
            response,
            "NỘI DUNG NỘI BỘ KHÔNG CÔNG KHAI",
        )

    def test_review_draft_missing_redirects_to_catalog(self):
        response = self.client.get(reverse("rentals:review"))
        self.assertRedirects(response, reverse("catalog:list"))

    def test_review_rejects_invalid_session_data(self):
        session = self.client.session
        session["rental_request"] = {"camera_id": "invalid"}
        session.save()

        response = self.client.get(reverse("rentals:review"))
        self.assertRedirects(response, reverse("catalog:list"))
        self.assertNotIn("rental_request", self.client.session)

    def test_review_rejects_changed_rate(self):
        self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.form_data(),
        )
        self.rate.amount = 150000
        self.rate.save(update_fields=["amount"])

        response = self.client.get(reverse("rentals:review"))
        self.assertRedirects(
            response,
            reverse("rentals:booking", args=[self.camera.slug]),
        )
        self.assertEqual(RentalOrder.objects.count(), 0)

    def test_review_cannot_submit_same_draft_twice(self):
        self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.form_data(),
        )
        self.client.post(
            reverse("rentals:review"),
            {"confirm": "yes"},
        )
        response = self.client.post(
            reverse("rentals:review"),
            {"confirm": "yes"},
        )
        self.assertRedirects(response, reverse("catalog:list"))
        self.assertEqual(RentalOrder.objects.count(), 1)


# KIỂM TRA LỊCH THUÊ VÀ SỐ LƯỢNG MÁY
class RentalCapacityTests(RentalTestData):
    def test_same_time_slot_cannot_exceed_available_units(self):
        start_at = timezone.now() + timedelta(days=3)
        self.make_order(start_at=start_at)

        self.assertFalse(
            has_capacity(
                self.camera,
                start_at,
                start_at + timedelta(hours=2),
                1,
            )
        )

    def test_back_to_back_bookings_do_not_conflict(self):
        start_at = timezone.now() + timedelta(days=3)
        self.make_order(
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
        )
        self.assertTrue(
            has_capacity(
                self.camera,
                start_at + timedelta(hours=2),
                start_at + timedelta(hours=4),
                1,
            )
        )

    def test_separate_reservations_do_not_get_added_together(self):
        self.camera.available_units = 2
        self.camera.save(update_fields=["available_units"])
        start_at = timezone.now() + timedelta(days=3)

        self.make_order(
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
        )
        self.make_order(
            start_at=start_at + timedelta(hours=3),
            end_at=start_at + timedelta(hours=4),
        )

        self.assertTrue(
            has_capacity(
                self.camera,
                start_at,
                start_at + timedelta(hours=5),
                1,
            )
        )

    def test_returned_order_does_not_reserve_camera(self):
        start_at = timezone.now() + timedelta(days=3)
        self.make_order(
            start_at=start_at,
            status=RentalOrder.Status.RETURNED,
        )
        self.assertTrue(
            has_capacity(
                self.camera,
                start_at,
                start_at + timedelta(hours=2),
                1,
            )
        )

    def test_overdue_rented_camera_remains_unavailable(self):
        start_at = timezone.now() - timedelta(days=2)
        self.make_order(
            start_at=start_at,
            end_at=start_at + timedelta(days=1),
            status=RentalOrder.Status.RENTED,
        )
        future = timezone.now() + timedelta(hours=2)

        self.assertFalse(
            has_capacity(
                self.camera,
                future,
                future + timedelta(hours=2),
                1,
            )
        )

    def test_invalid_quantity_or_time_is_rejected(self):
        start_at = timezone.now() + timedelta(days=2)
        end_at = start_at + timedelta(hours=3)

        self.assertFalse(
            has_capacity(self.camera, start_at, end_at, 0)
        )
        self.assertFalse(
            has_capacity(self.camera, start_at, end_at, 2)
        )
        self.assertFalse(
            has_capacity(self.camera, end_at, start_at, 1)
        )


# QUY TRÌNH XỬ LÝ ĐƠN VÀ TIỀN CỌC
class RentalServiceTests(RentalTestData):
    def test_customer_cannot_update_order_status(self):
        order = self.make_order()

        with self.assertRaises(PermissionDenied):
            update_order_status(
                order_id=order.pk,
                actor=self.customer,
                new_status=RentalOrder.Status.CONFIRMED,
            )

    def test_cannot_confirm_order_without_confirmed_deposit(self):
        order = self.make_order()

        with self.assertRaises(ValidationError):
            update_order_status(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.Status.CONFIRMED,
            )

        order.refresh_from_db()
        self.assertEqual(
            order.status,
            RentalOrder.Status.PENDING,
        )

    def test_confirm_order_after_setting_deposit(self):
        order = self.make_order()

        update_order_deposit(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.DepositStatus.DUE,
            amount=300000,
        )

        updated = update_order_status(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.Status.CONFIRMED,
        )

        self.assertEqual(
            updated.status,
            RentalOrder.Status.CONFIRMED,
        )
        self.assertEqual(updated.deposit_amount, 300000)
        self.assertTrue(
            RentalEvent.objects.filter(order=order).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                order_id=order.pk,
            ).exists()
        )

    def test_cannot_skip_state_transitions(self):
        order = self.make_order()

        with self.assertRaises(ValidationError):
            update_order_status(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.Status.RENTED,
            )

    def test_handover_requires_camera_condition(self):
        order = self.make_order(
            status=RentalOrder.Status.PREPARING
        )

        with self.assertRaises(ValidationError):
            update_order_status(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.Status.RENTED,
            )

        updated = update_order_status(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.Status.RENTED,
            condition_out="Thân máy và pin hoạt động bình thường.",
        )

        self.assertIsNotNone(updated.handover_at)
        self.assertEqual(
            updated.status,
            RentalOrder.Status.RENTED,
        )

    def test_return_requires_condition_and_return_method(self):
        order = self.make_order(
            status=RentalOrder.Status.RENTED
        )

        with self.assertRaises(ValidationError):
            update_order_status(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.Status.RETURNED,
            )

        updated = update_order_status(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.Status.RETURNED,
            condition_in="Đã kiểm tra máy, không phát hiện hư hỏng.",
            return_method="Trả tại cửa hàng",
        )

        self.assertEqual(
            updated.status,
            RentalOrder.Status.RETURNED,
        )
        self.assertIsNotNone(updated.returned_at)

    def test_rejection_requires_customer_reason(self):
        order = self.make_order()

        with self.assertRaises(ValidationError):
            update_order_status(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.Status.REJECTED,
            )

        updated = update_order_status(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.Status.REJECTED,
            customer_message=(
                "Cửa hàng không đủ máy trong khung giờ yêu cầu."
            ),
        )

        self.assertEqual(
            updated.status,
            RentalOrder.Status.REJECTED,
        )
        self.assertTrue(
            Notification.objects.filter(
                order_id=order.pk
            ).exists()
        )

    def test_deposit_requires_positive_amount(self):
        order = self.make_order()

        with self.assertRaises(ValidationError):
            update_order_deposit(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.DepositStatus.DUE,
                amount=0,
            )

    def test_deposit_can_be_received_and_refunded(self):
        order = self.make_order()

        update_order_deposit(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.DepositStatus.DUE,
            amount=300000,
        )

        update_order_deposit(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.DepositStatus.RECEIVED,
        )

        updated = update_order_deposit(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.DepositStatus.REFUNDED,
        )

        self.assertEqual(
            updated.deposit_status,
            RentalOrder.DepositStatus.REFUNDED,
        )
        self.assertEqual(updated.deposit_amount, 300000)

    def test_deduction_requires_explanation(self):
        order = self.make_order(
            deposit_status=RentalOrder.DepositStatus.RECEIVED,
            deposit_amount=300000,
        )

        with self.assertRaises(ValidationError):
            update_order_deposit(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.DepositStatus.DEDUCTED,
            )

        updated = update_order_deposit(
            order_id=order.pk,
            actor=self.manager,
            new_status=RentalOrder.DepositStatus.DEDUCTED,
            customer_message=(
                "Khấu trừ cọc theo biên bản kiểm tra thiết bị."
            ),
        )

        self.assertEqual(
            updated.deposit_status,
            RentalOrder.DepositStatus.DEDUCTED,
        )

    def test_deposit_amount_cannot_change_after_receipt(self):
        order = self.make_order(
            deposit_status=RentalOrder.DepositStatus.RECEIVED,
            deposit_amount=300000,
        )

        with self.assertRaises(ValidationError):
            update_order_deposit(
                order_id=order.pk,
                actor=self.manager,
                new_status=RentalOrder.DepositStatus.REFUNDED,
                amount=400000,
            )

        order.refresh_from_db()
        self.assertEqual(order.deposit_amount, 300000)


# PHÂN QUYỀN VÀ GIAO DIỆN NHÂN VIÊN
class RentalStaffViewTests(RentalTestData):
    def setUp(self):
        self.client.force_login(self.manager)

    def test_manager_can_open_staff_order_list_and_detail(self):
        order = self.make_order()

        response = self.client.get(
            reverse("rentals:staff_orders")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_code)

        detail = self.client.get(
            reverse(
                "rentals:staff_order_detail",
                args=[order.pk],
            )
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, order.order_code)

    def test_customer_cannot_open_staff_pages(self):
        self.client.force_login(self.customer)
        response = self.client.get(
            reverse("rentals:staff_orders")
        )
        self.assertEqual(response.status_code, 302)

    def test_view_only_employee_cannot_modify_order(self):
        order = self.make_order()
        self.client.force_login(self.viewer)

        self.assertEqual(
            self.client.get(
                reverse(
                    "rentals:staff_order_detail",
                    args=[order.pk],
                )
            ).status_code,
            200,
        )

        response = self.client.post(
            reverse(
                "rentals:staff_order_status",
                args=[order.pk],
            ),
            {"status": RentalOrder.Status.CONFIRMED},
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(
            order.status,
            RentalOrder.Status.PENDING,
        )

    def test_staff_list_filters_by_status_and_search(self):
        pending = self.make_order(
            status=RentalOrder.Status.PENDING
        )
        returned = self.make_order(
            status=RentalOrder.Status.RETURNED
        )

        response = self.client.get(
            reverse("rentals:staff_orders"),
            {
                "status": "pending",
                "q": pending.order_code,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pending.order_code)
        self.assertNotContains(response, returned.order_code)

    def test_status_endpoint_confirm_after_deposit(self):
        order = self.make_order(
            deposit_amount=300000,
            deposit_status=RentalOrder.DepositStatus.DUE,
        )

        response = self.client.post(
            reverse(
                "rentals:staff_order_status",
                args=[order.pk],
            ),
            {"status": RentalOrder.Status.CONFIRMED},
        )

        self.assertRedirects(
            response,
            reverse(
                "rentals:staff_order_detail",
                args=[order.pk],
            ),
        )

        order.refresh_from_db()
        self.assertEqual(
            order.status,
            RentalOrder.Status.CONFIRMED,
        )

    def test_deposit_endpoint_records_amount(self):
        order = self.make_order()

        response = self.client.post(
            reverse(
                "rentals:staff_order_deposit",
                args=[order.pk],
            ),
            {
                "deposit_status": RentalOrder.DepositStatus.DUE,
                "deposit_amount": "300000",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "rentals:staff_order_detail",
                args=[order.pk],
            ),
        )

        order.refresh_from_db()
        self.assertEqual(
            order.deposit_status,
            RentalOrder.DepositStatus.DUE,
        )
        self.assertEqual(order.deposit_amount, 300000)

    def test_staff_update_endpoints_accept_post_only(self):
        order = self.make_order()

        self.assertEqual(
            self.client.get(
                reverse(
                    "rentals:staff_order_status",
                    args=[order.pk],
                )
            ).status_code,
            405,
        )

        self.assertEqual(
            self.client.get(
                reverse(
                    "rentals:staff_order_deposit",
                    args=[order.pk],
                )
            ).status_code,
            405,
        )


# KIỂM TRA BIỂU MẪU QUẢN TRỊ
class RentalAdminFormTests(RentalTestData):
    def test_admin_cannot_confirm_overlapping_booking(self):
        start_at = timezone.now() + timedelta(days=3)
        first = self.make_order(start_at=start_at)
        self.make_order(start_at=start_at)

        data = model_to_dict(first)
        data.update(
            {
                "status": RentalOrder.Status.CONFIRMED,
                "deposit_amount": 300000,
                "deposit_status": RentalOrder.DepositStatus.DUE,
            }
        )

        form = RentalOrderAdminForm(
            data=data,
            instance=first,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_admin_cannot_skip_order_states(self):
        order = self.make_order()
        data = model_to_dict(order)
        data["status"] = RentalOrder.Status.RENTED

        form = RentalOrderAdminForm(
            data=data,
            instance=order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_admin_requires_reason_when_rejecting(self):
        order = self.make_order()
        data = model_to_dict(order)
        data["status"] = RentalOrder.Status.REJECTED

        form = RentalOrderAdminForm(
            data=data,
            instance=order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("customer_message", form.errors)

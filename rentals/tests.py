from datetime import timedelta

from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile, Notification

from .models import RentalOrder
from .admin import RentalOrderAdminForm

User = get_user_model()


class RentalFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="customer@example.test",
            email="customer@example.test",
            first_name="Khách hàng",
            password="Secure-test-Password-123!",
        )
        CustomerProfile.objects.create(user=cls.user, phone="0900000000")
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

    def rental_form_data(self, start_at=None):
        if start_at is None:
            start_at = timezone.localtime(timezone.now() + timedelta(days=2))
            start_at = start_at.replace(hour=10, minute=0, second=0, microsecond=0)
        return {
            "rate": str(self.rate.pk),
            "start_at": start_at.strftime("%Y-%m-%dT%H:%M"),
            "quantity": "1",
            "delivery_method": RentalOrder.DeliveryMethod.PICKUP,
            "delivery_address": "",
            "customer_note": "",
            "accept_policy": "on",
        }

    def setUp(self):
        self.client.force_login(self.user)

    def test_booking_review_confirm_creates_pending_order_and_notification(self):
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            self.rental_form_data(),
        )
        self.assertRedirects(response, reverse("rentals:review"))
        response = self.client.post(reverse("rentals:review"), {"confirm": "yes"})
        order = RentalOrder.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse("rentals:success", args=[order.pk]),
        )
        self.assertEqual(order.status, RentalOrder.Status.PENDING)
        self.assertEqual(order.rental_total, 130000)
        self.assertEqual(
            order.end_at - order.start_at,
            timedelta(hours=23),
        )
        self.assertTrue(Notification.objects.filter(user=self.user).exists())

    def test_overlapping_request_is_rejected(self):
        data = self.rental_form_data()
        start_at = timezone.make_aware(
            timezone.datetime.strptime(data["start_at"], "%Y-%m-%dT%H:%M")
        )
        RentalOrder.objects.create(
            user=self.user,
            camera=self.camera,
            rate=self.rate,
            start_at=start_at,
            end_at=start_at + timedelta(hours=23),
            rate_label=self.rate.label,
            duration_hours=self.rate.duration_hours,
            rental_total=self.rate.amount,
            contact_name="Khách hàng",
            contact_phone="0900000000",
        )
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "không còn đủ số lượng")
        self.assertEqual(RentalOrder.objects.count(), 1)

    def test_six_hour_rental_requires_a_documented_start_slot(self):
        data = self.rental_form_data()
        data["rate"] = str(self.short_rate.pk)
        response = self.client.post(
            reverse("rentals:booking", args=[self.camera.slug]),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "08:00 hoặc 15:00")
        self.assertEqual(RentalOrder.objects.count(), 0)

    def test_customers_cannot_view_another_users_order(self):
        other = User.objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="Secure-test-Password-123!",
        )
        start_at = timezone.now() + timedelta(days=3)
        order = RentalOrder.objects.create(
            user=other,
            camera=self.camera,
            rate=self.rate,
            start_at=start_at,
            end_at=start_at + timedelta(hours=23),
            rate_label=self.rate.label,
            duration_hours=self.rate.duration_hours,
            rental_total=self.rate.amount,
            contact_name="Khách khác",
            contact_phone="0900000001",
        )
        response = self.client.get(reverse("rentals:detail", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_guests_are_redirected_to_sign_in_before_booking(self):
        self.client.logout()
        response = self.client.get(
            reverse("rentals:booking", args=[self.camera.slug])
        )
        self.assertRedirects(
            response,
            f"{reverse('customers:login')}?next={reverse('rentals:booking', args=[self.camera.slug])}",
        )

    def test_booking_form_selects_store_pickup_by_default(self):
        response = self.client.get(
            reverse("rentals:booking", args=[self.camera.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["delivery_method"].value(),
            RentalOrder.DeliveryMethod.PICKUP,
        )

    def test_staff_cannot_confirm_a_schedule_conflicting_with_another_request(self):
        start_at = timezone.now() + timedelta(days=4)
        first = RentalOrder.objects.create(
            user=self.user,
            camera=self.camera,
            rate=self.rate,
            start_at=start_at,
            end_at=start_at + timedelta(hours=23),
            rate_label=self.rate.label,
            duration_hours=self.rate.duration_hours,
            rental_total=self.rate.amount,
            contact_name="Khách hàng",
            contact_phone="0900000000",
        )
        RentalOrder.objects.create(
            user=self.user,
            camera=self.camera,
            rate=self.rate,
            start_at=start_at,
            end_at=start_at + timedelta(hours=23),
            rate_label=self.rate.label,
            duration_hours=self.rate.duration_hours,
            rental_total=self.rate.amount,
            contact_name="Khách hàng",
            contact_phone="0900000000",
        )
        data = model_to_dict(first)
        data["status"] = RentalOrder.Status.CONFIRMED
        form = RentalOrderAdminForm(data=data, instance=first)
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

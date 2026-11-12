
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile, Notification
from rentals.models import RentalOrder

from .models import Feedback

User = get_user_model()


# KIỂM THỬ DUYỆT PHẢN HỒI
class FeedbackStaffTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="owner-feedback",
            email="ownerfeedback@test.local",
            password="StrongPassword!123",
        )

        self.user = User.objects.create_user(
            username="feedback-user",
            email="feedbackuser@test.local",
            password="StrongPassword!123",
        )

        CustomerProfile.objects.create(
            user=self.user,
            phone="0901112223",
        )

        self.camera = Camera.objects.create(
            name="Canon Feedback Test",
            slug="canon-feedback-test",
            brand=Camera.Brand.CANON,
            image="images/products/canonm10.jpg",
            available_units=1,
        )

        self.rate = RentalRate.objects.create(
            camera=self.camera,
            label="1 ngày",
            duration_hours=23,
            amount=130000,
        )

        self.order = RentalOrder.objects.create(
            user=self.user,
            camera=self.camera,
            rate=self.rate,
            start_at=timezone.now() - timedelta(days=3),
            end_at=timezone.now() - timedelta(days=2),
            status=RentalOrder.Status.RETURNED,
            rate_label=self.rate.label,
            duration_hours=23,
            rental_total=130000,
            contact_name="Khách hàng",
            contact_phone="0901112223",
        )

        self.entry = Feedback.objects.create(
            user=self.user,
            order=self.order,
            camera=self.camera,
            rating=5,
            content="Chất lượng máy và dịch vụ rất tốt",
            is_published=False,
        )

    def test_public_cannot_see_pending_feedback(self):
        response = self.client.get(
            reverse(
                "feedback:camera",
                args=[self.camera.slug],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            self.entry.content,
        )

    def test_manager_approval_makes_feedback_public(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse(
                "feedback:moderate",
                args=[self.entry.pk],
            ),
            {
                "is_published": "on",
                "shop_reply": "Cảm ơn bạn đã đánh giá",
            },
        )

        self.assertRedirects(
            response,
            reverse("feedback:manage"),
        )

        self.entry.refresh_from_db()

        self.assertTrue(self.entry.is_published)
        self.assertEqual(
            self.entry.shop_reply,
            "Cảm ơn bạn đã đánh giá",
        )

        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                order_id=self.order.pk,
            ).exists()
        )

        self.client.logout()

        response = self.client.get(
            reverse(
                "feedback:camera",
                args=[self.camera.slug],
            )
        )

        self.assertContains(
            response,
            self.entry.content,
        )

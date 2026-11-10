from base64 import b64decode
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile
from rentals.models import RentalOrder

from .models import Feedback

User = get_user_model()


class CustomerFeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="reviewer@example.test",
            email="reviewer@example.test",
            password="Strong-password-123!",
        )
        CustomerProfile.objects.create(user=cls.user, phone="0900000000")
        cls.camera = Camera.objects.create(
            name="Canon M10",
            slug="canon-m10",
            brand=Camera.Brand.CANON,
            image="images/products/canonm10.jpg",
        )
        cls.rate = RentalRate.objects.create(
            camera=cls.camera,
            label="1 ngày",
            duration_hours=23,
            amount=130000,
        )
        cls.order = RentalOrder.objects.create(
            user=cls.user,
            camera=cls.camera,
            rate=cls.rate,
            status=RentalOrder.Status.RETURNED,
            start_at=timezone.now() - timedelta(days=3),
            end_at=timezone.now() - timedelta(days=2),
            rate_label=cls.rate.label,
            duration_hours=cls.rate.duration_hours,
            rental_total=cls.rate.amount,
            contact_name="Khách thuê",
            contact_phone="0900000000",
            returned_at=timezone.now() - timedelta(days=2),
        )

    def test_only_completed_order_owner_can_submit_and_feedback_is_unpublished(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("feedback:create", args=[self.order.pk]),
            {"rating": "5", "content": "Máy được chuẩn bị rất cẩn thận."},
        )
        self.assertRedirects(response, reverse("feedback:list"))
        entry = Feedback.objects.get(order=self.order)
        self.assertFalse(entry.is_published)
        self.assertEqual(entry.camera, self.camera)

    def test_feedback_is_not_public_until_approved(self):
        entry = Feedback.objects.create(
            user=self.user,
            order=self.order,
            camera=self.camera,
            rating=5,
            content="Máy được chuẩn bị rất cẩn thận.",
        )
        response = self.client.get(reverse("feedback:list"))
        self.assertNotContains(response, entry.content)
        entry.is_published = True
        entry.save(update_fields=["is_published"])
        response = self.client.get(reverse("feedback:list"))
        self.assertContains(response, entry.content)

    def test_unreturned_order_cannot_receive_feedback(self):
        self.order.status = RentalOrder.Status.RENTED
        self.order.save(update_fields=["status"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("feedback:create", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_unpublished_feedback_image_is_private_until_approved(self):
        image = b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "gN8AAAAASUVORK5CYII="
        )
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            entry = Feedback.objects.create(
                user=self.user,
                order=self.order,
                camera=self.camera,
                rating=5,
                content="Máy được chuẩn bị rất cẩn thận.",
            )
            entry.photo.save(
                "feedback.png",
                SimpleUploadedFile("feedback.png", image, content_type="image/png"),
                save=True,
            )
            self.assertEqual(self.client.get(f"/media/{entry.photo.name}").status_code, 404)
            url = reverse("feedback:photo", args=[entry.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response.close()
            self.client.logout()
            entry.is_published = True
            entry.save(update_fields=["is_published"])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            response.close()

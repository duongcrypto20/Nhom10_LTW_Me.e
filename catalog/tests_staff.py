
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import CustomerProfile
from .models import Camera

User = get_user_model()


# KIỂM THỬ QUẢN LÝ MÁY ẢNH
class CatalogStaffTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser(
            username="owner-test",
            email="owner@test.local",
            password="StrongPassword!123",
        )

        self.customer = User.objects.create_user(
            username="buyer-test",
            email="buyer@test.local",
            password="StrongPassword!123",
        )

        CustomerProfile.objects.create(
            user=self.customer
        )

    def test_guest_cannot_manage_cameras(self):
        response = self.client.get(
            reverse("catalog:manage_cameras")
        )
        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_manage_cameras(self):
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("catalog:manage_cameras")
        )
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_add_and_edit_camera(self):
        self.client.force_login(self.manager)

        data = {
            "name": "Máy thử nghiệp vụ",
            "slug": "may-thu-nghiep-vu",
            "brand": Camera.Brand.CANON,
            "image": "images/products/canonm10.jpg",
            "description": "Máy ảnh kiểm thử",
            "available_units": 2,
            "deposit_amount": 300000,
            "is_active": "on",
        }

        response = self.client.post(
            reverse("catalog:create_camera"),
            data,
        )

        self.assertRedirects(
            response,
            reverse("catalog:manage_cameras"),
        )

        camera = Camera.objects.get(
            slug="may-thu-nghiep-vu"
        )

        data["name"] = "Máy thử đã cập nhật"
        data["available_units"] = 3

        response = self.client.post(
            reverse("catalog:edit_camera", args=[camera.pk]),
            data,
        )

        self.assertRedirects(
            response,
            reverse("catalog:manage_cameras"),
        )

        camera.refresh_from_db()

        self.assertEqual(camera.available_units, 3)
        self.assertEqual(
            camera.name,
            "Máy thử đã cập nhật",
        )

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Address, CustomerProfile

User = get_user_model()


class CustomerAccountTests(TestCase):
    def test_register_creates_email_login_and_profile(self):
        response = self.client.post(
            reverse("customers:register"),
            {
                "first_name": "Nguyễn An",
                "email": "AN@example.test",
                "phone": "0900000000",
                "password1": "Strong-password-123!",
                "password2": "Strong-password-123!",
            },
        )
        user = User.objects.get(email="an@example.test")
        self.assertRedirects(response, reverse("customers:profile"))
        self.assertEqual(user.username, "an@example.test")
        self.assertEqual(user.customer_profile.phone, "0900000000")

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username="first@example.test",
            email="first@example.test",
            password="Strong-password-123!",
        )
        response = self.client.post(
            reverse("customers:register"),
            {
                "first_name": "Nguyễn An",
                "email": "FIRST@example.test",
                "phone": "0900000001",
                "password1": "Strong-password-123!",
                "password2": "Strong-password-123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "đã được sử dụng")
        self.assertEqual(User.objects.count(), 1)

    def test_login_rejects_external_redirect_target(self):
        User.objects.create_user(
            username="login@example.test",
            email="login@example.test",
            password="Strong-password-123!",
        )
        response = self.client.post(
            reverse("customers:login") + "?next=https://outside.invalid/",
            {
                "username": "login@example.test",
                "password": "Strong-password-123!",
                "next": "https://outside.invalid/",
            },
        )
        self.assertRedirects(response, reverse("customers:profile"))

    def test_address_default_is_unique_per_user(self):
        user = User.objects.create_user(
            username="address@example.test",
            email="address@example.test",
            password="Strong-password-123!",
        )
        first = Address.objects.create(
            user=user,
            label="Nhà",
            recipient="Nguyễn An",
            phone="0900000000",
            street="Đường A",
            district="Quận B",
            city="Đà Nẵng",
            is_default=True,
        )
        second = Address.objects.create(
            user=user,
            label="Văn phòng",
            recipient="Nguyễn An",
            phone="0900000000",
            street="Đường C",
            district="Quận D",
            city="Đà Nẵng",
            is_default=True,
        )
        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

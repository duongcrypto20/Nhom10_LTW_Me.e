
from base64 import b64decode
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Camera, RentalRate
from customers.models import CustomerProfile, Notification
from rentals.models import RentalOrder

from .models import Feedback, validate_photo_size

User = get_user_model()


# KIỂM THỬ PHẢN HỒI KHÁCH HÀNG
class CustomerFeedbackTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="reviewer@example.test",
            email="reviewer@example.test",
            password="Strong-password-123!",
        )

        CustomerProfile.objects.create(
            user=cls.user,
            phone="0900000000",
        )

        cls.other_user = User.objects.create_user(
            username="other@example.test",
            email="other@example.test",
            password="Strong-password-123!",
        )

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

    def create_feedback(self, **kwargs):
        data = {
            "user": self.user,
            "order": self.order,
            "camera": self.camera,
            "rating": 5,
            "content": "Máy được chuẩn bị rất cẩn thận.",
        }

        data.update(kwargs)

        return Feedback.objects.create(**data)

    def test_customer_can_submit_feedback_for_completed_order(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("feedback:create", args=[self.order.pk]),
            {
                "rating": "5",
                "content": "Máy được chuẩn bị rất cẩn thận.",
            },
        )

        self.assertRedirects(
            response,
            reverse("feedback:list"),
        )

        entry = Feedback.objects.get(order=self.order)

        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.camera, self.camera)
        self.assertEqual(entry.rating, 5)
        self.assertFalse(entry.is_published)

    def test_guest_must_login_before_submitting_feedback(self):
        response = self.client.get(
            reverse("feedback:create", args=[self.order.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("customers:login"),
            response.url,
        )

    def test_other_customer_cannot_review_another_users_order(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("feedback:create", args=[self.order.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_unreturned_order_cannot_receive_feedback(self):
        self.order.status = RentalOrder.Status.RENTED
        self.order.save(update_fields=["status"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("feedback:create", args=[self.order.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_one_order_can_only_receive_one_feedback(self):
        self.create_feedback()

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("feedback:create", args=[self.order.pk]),
            {
                "rating": "4",
                "content": "Trải nghiệm thuê máy rất tốt.",
            },
        )

        self.assertRedirects(
            response,
            reverse("rentals:detail", args=[self.order.pk]),
        )

        self.assertEqual(
            Feedback.objects.filter(order=self.order).count(),
            1,
        )

    def test_feedback_content_must_have_at_least_ten_characters(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("feedback:create", args=[self.order.pk]),
            {
                "rating": "5",
                "content": "Tốt",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Feedback.objects.filter(order=self.order).exists()
        )

        self.assertContains(
            response,
            "Nội dung phản hồi phải có ít nhất 10 ký tự.",
        )

    def test_feedback_rating_must_be_between_one_and_five(self):
        entry = Feedback(
            user=self.user,
            order=self.order,
            camera=self.camera,
            rating=6,
            content="Trải nghiệm thuê máy rất tốt.",
        )

        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_feedback_model_rejects_wrong_customer(self):
        entry = Feedback(
            user=self.other_user,
            order=self.order,
            camera=self.camera,
            rating=5,
            content="Trải nghiệm thuê máy rất tốt.",
        )

        with self.assertRaises(ValidationError):
            entry.full_clean()

    def test_feedback_is_not_public_until_approved(self):
        entry = self.create_feedback()

        response = self.client.get(
            reverse("feedback:list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, entry.content)

        entry.is_published = True
        entry.save(update_fields=["is_published"])

        response = self.client.get(
            reverse("feedback:list")
        )

        self.assertContains(response, entry.content)
        self.assertContains(response, entry.camera.name)

    def test_feedback_can_be_filtered_by_camera(self):
        entry = self.create_feedback(is_published=True)

        response = self.client.get(
            reverse("feedback:camera", args=[self.camera.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, entry.content)

        self.assertEqual(
            response.context["selected_camera"],
            self.camera,
        )

    def test_feedback_camera_returns_404_for_unknown_camera(self):
        response = self.client.get(
            reverse("feedback:camera", args=["khong-ton-tai"])
        )

        self.assertEqual(response.status_code, 404)

    def test_uploaded_photo_must_not_exceed_two_megabytes(self):
        oversized_photo = SimpleUploadedFile(
            "feedback.jpg",
            b"x" * (2 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            validate_photo_size(oversized_photo)

    def test_unpublished_feedback_image_is_private(self):
        image = b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "gN8AAAAASUVORK5CYII="
        )

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                entry = self.create_feedback()

                entry.photo.save(
                    "feedback.png",
                    SimpleUploadedFile(
                        "feedback.png",
                        image,
                        content_type="image/png",
                    ),
                    save=True,
                )

                photo_url = reverse(
                    "feedback:photo",
                    args=[entry.pk],
                )

                response = self.client.get(photo_url)
                self.assertEqual(response.status_code, 404)

                self.client.force_login(self.other_user)

                response = self.client.get(photo_url)
                self.assertEqual(response.status_code, 404)

                self.client.force_login(self.user)

                response = self.client.get(photo_url)
                self.assertEqual(response.status_code, 200)
                response.close()

                self.client.logout()

                entry.is_published = True
                entry.save(update_fields=["is_published"])

                response = self.client.get(photo_url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response["Cache-Control"],
                    "private, no-store",
                )
                response.close()


# KIỂM THỬ QUẢN LÝ PHẢN HỒI NHÂN VIÊN
class StaffFeedbackTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="customer@example.test",
            email="customer@example.test",
            password="Strong-password-123!",
        )

        CustomerProfile.objects.create(
            user=cls.customer,
            phone="0900000000",
        )

        cls.staff = User.objects.create_user(
            username="staff@example.test",
            email="staff@example.test",
            password="Strong-password-123!",
        )

        CustomerProfile.objects.create(
            user=cls.staff,
            phone="0911111111",
            role=CustomerProfile.Role.STAFF,
        )

        cls.camera = Camera.objects.create(
            name="Canon M50",
            slug="canon-m50",
            brand=Camera.Brand.CANON,
            image="images/products/canonm50.jpg",
        )

        cls.rate = RentalRate.objects.create(
            camera=cls.camera,
            label="1 ngày",
            duration_hours=23,
            amount=160000,
        )

        cls.order = RentalOrder.objects.create(
            user=cls.customer,
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

    def create_feedback(self, **kwargs):
        data = {
            "user": self.customer,
            "order": self.order,
            "camera": self.camera,
            "rating": 5,
            "content": "Chất lượng máy ảnh rất tốt.",
        }

        data.update(kwargs)

        return Feedback.objects.create(**data)

    def test_customer_cannot_access_feedback_management(self):
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("feedback:manage")
        )

        self.assertEqual(response.status_code, 302)

    def test_staff_can_access_feedback_management(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:manage")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "feedback/staff_list.html",
        )

    def test_staff_can_view_unpublished_feedback(self):
        entry = self.create_feedback()

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:manage")
        )

        self.assertContains(response, entry.content[:25])
        self.assertContains(response, entry.camera.name)

    def test_staff_can_filter_feedback_by_status(self):
        entry = self.create_feedback(is_published=False)

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:manage"),
            {"status": "unpublished"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            entry,
            response.context["entries"].object_list,
        )

        response = self.client.get(
            reverse("feedback:manage"),
            {"status": "published"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            entry,
            response.context["entries"].object_list,
        )

    def test_staff_can_filter_feedback_by_rating(self):
        entry = self.create_feedback(rating=4)

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:manage"),
            {"rating": "4"},
        )

        self.assertIn(
            entry,
            response.context["entries"].object_list,
        )

        response = self.client.get(
            reverse("feedback:manage"),
            {"rating": "5"},
        )

        self.assertNotIn(
            entry,
            response.context["entries"].object_list,
        )

    def test_staff_can_search_feedback_by_order_code(self):
        entry = self.create_feedback()

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:manage"),
            {"q": self.order.order_code},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            entry,
            response.context["entries"].object_list,
        )

    def test_staff_can_approve_feedback(self):
        entry = self.create_feedback(is_published=False)

        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("feedback:moderate", args=[entry.pk]),
            {
                "is_published": "on",
                "shop_reply": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("feedback:manage"),
        )

        entry.refresh_from_db()
        self.assertTrue(entry.is_published)

        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                order_id=self.order.pk,
                title="Phản hồi đã được duyệt",
            ).exists()
        )

    def test_staff_can_hide_published_feedback(self):
        entry = self.create_feedback(is_published=True)

        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("feedback:moderate", args=[entry.pk]),
            {
                "shop_reply": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("feedback:manage"),
        )

        entry.refresh_from_db()
        self.assertFalse(entry.is_published)

        self.client.logout()

        response = self.client.get(
            reverse("feedback:list")
        )

        self.assertNotContains(response, entry.content)

    def test_staff_can_reply_to_feedback(self):
        entry = self.create_feedback(is_published=True)

        self.client.force_login(self.staff)

        reply = (
            "Cảm ơn bạn đã sử dụng dịch vụ "
            "của ME.E Digitalcam."
        )

        response = self.client.post(
            reverse("feedback:moderate", args=[entry.pk]),
            {
                "is_published": "on",
                "shop_reply": reply,
            },
        )

        self.assertRedirects(
            response,
            reverse("feedback:manage"),
        )

        entry.refresh_from_db()
        self.assertEqual(entry.shop_reply, reply)

        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                title="Cửa hàng đã trả lời phản hồi",
            ).exists()
        )

        self.client.logout()

        response = self.client.get(
            reverse("feedback:list")
        )

        self.assertContains(response, reply)

    def test_approving_same_feedback_twice_does_not_duplicate_notification(self):
        entry = self.create_feedback(is_published=False)

        self.client.force_login(self.staff)

        url = reverse(
            "feedback:moderate",
            args=[entry.pk],
        )

        data = {
            "is_published": "on",
            "shop_reply": "",
        }

        self.client.post(url, data)
        self.client.post(url, data)

        notification_count = Notification.objects.filter(
            user=self.customer,
            title="Phản hồi đã được duyệt",
            order_id=self.order.pk,
        ).count()

        self.assertEqual(notification_count, 1)

    def test_staff_can_view_feedback_edit_page(self):
        entry = self.create_feedback()

        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("feedback:moderate", args=[entry.pk])
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "feedback/staff_edit.html",
        )

        self.assertContains(
            response,
            entry.camera.name,
        )

    def test_staff_without_change_permission_cannot_moderate(self):
        read_only_staff = User.objects.create_user(
            username="readonly@example.test",
            email="readonly@example.test",
            password="Strong-password-123!",
            is_staff=True,
        )

        permission = Permission.objects.get(
            content_type__app_label="feedback",
            codename="view_feedback",
        )

        read_only_staff.user_permissions.add(permission)

        self.client.force_login(read_only_staff)

        entry = self.create_feedback()

        response = self.client.get(
            reverse("feedback:manage")
        )

        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("feedback:moderate", args=[entry.pk]),
            {
                "is_published": "on",
                "shop_reply": "Đã kiểm tra phản hồi.",
            },
        )

        self.assertEqual(response.status_code, 403)

        entry.refresh_from_db()
        self.assertFalse(entry.is_published)

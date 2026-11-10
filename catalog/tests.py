from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Camera, RentalRate


class CatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", verbosity=0)

    def test_seed_loads_all_cameras_and_source_prices(self):
        self.assertEqual(Camera.objects.count(), 12)
        m10 = Camera.objects.get(slug="canon-m10")
        self.assertEqual(
            list(m10.rates.values_list("amount", flat=True)),
            [90000, 130000, 250000, 370000],
        )
        self.assertTrue((Path(__file__).resolve().parent.parent / "static" / m10.image).exists())

    def test_catalog_search_filters_by_camera_name(self):
        response = self.client.get(reverse("catalog:list"), {"q": "M10"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Canon M10")
        self.assertNotContains(response, "Canon R50")

    def test_product_detail_contains_all_rental_periods(self):
        response = self.client.get(reverse("catalog:detail", args=["canon-m10"]))
        self.assertEqual(response.status_code, 200)
        for label in ("6 giờ", "1 ngày", "2 ngày", "3 ngày"):
            self.assertContains(response, label)

    def test_policy_page_uses_supplied_price_material(self):
        response = self.client.get(reverse("catalog:policies"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "700.000đ")
        self.assertContains(response, "50.000đ")

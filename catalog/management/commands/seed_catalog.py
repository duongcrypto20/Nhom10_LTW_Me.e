from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import Camera, RentalRate


CAMERAS = [
    ("Canon M10", "Canon", "canonm10.jpg", [90000, 130000, 250000, 370000]),
    ("Canon M50", "Canon", "canonm50.jpg", [120000, 160000, 310000, 460000]),
    ("Canon R50", "Canon", "canonr50.png", [180000, 220000, 430000, 640000]),
    ("Fujifilm XA3", "Fujifilm", "fujifilm_x_a3_review.png", [110000, 150000, 290000, 430000]),
    ("Fujifilm XT100", "Fujifilm", "fujixt100.png", [150000, 190000, 370000, 550000]),
    ("Fujifilm XT10", "Fujifilm", "fujixt10.png", [140000, 180000, 350000, 520000]),
    ("Fujifilm XT20", "Fujifilm", "fujixt20.png", [180000, 220000, 430000, 640000]),
    ("Fujifilm XT30", "Fujifilm", "fujixt30.png", [200000, 270000, 530000, 790000]),
    ("Fujifilm XS10", "Fujifilm", "fujix-s10.png", [260000, 320000, 630000, 940000]),
    ("Fujifilm XS20", "Fujifilm", "fujix-s20.png", [350000, 400000, 790000, 1180000]),
    ("Fujifilm X100V", "Fujifilm", "fujix100v.jpg", [320000, 390000, 770000, 1150000]),
    ("Fujifilm XM5", "Fujifilm", "fujiXM5.jpg", [250000, 300000, 590000, 880000]),
]
RATE_LABELS = [
    ("6 giờ", 6),
    ("1 ngày", 23),
    ("2 ngày", 47),
    ("3 ngày", 71),
]


class Command(BaseCommand):
    help = "Tạo/cập nhật 12 máy ảnh và bảng giá từ tài liệu dự án."

    def handle(self, *args, **options):
        for name, brand, image, prices in CAMERAS:
            camera, _ = Camera.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "brand": brand,
                    "image": f"images/products/{image}",
                    "description": (
                        f"{name} cho thuê tại ME.E Digitalcam. "
                        "Chọn thời lượng và ngày nhận máy để gửi yêu cầu."
                    ),
                    "is_active": True,
                },
            )
            for index, ((label, hours), amount) in enumerate(
                zip(RATE_LABELS, prices, strict=True)
            ):
                RentalRate.objects.update_or_create(
                    camera=camera,
                    duration_hours=hours,
                    defaults={
                        "label": label,
                        "amount": amount,
                        "sort_order": index,
                        "is_active": True,
                    },
                )
        self.stdout.write(self.style.SUCCESS("Loaded 12 cameras and rental rates."))

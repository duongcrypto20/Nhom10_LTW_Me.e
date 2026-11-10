from django.db.models import Min, Q
from django.shortcuts import get_object_or_404, render

from feedback.models import Feedback
from .models import Camera


def home(request):
    cameras = (
        Camera.objects.filter(is_active=True)
        .prefetch_related("rates")
        .order_by("brand", "name")[:8]
    )
    reviews = (
        Feedback.objects.filter(is_published=True)
        .select_related("user", "camera")
        .order_by("-created_at")[:3]
    )
    return render(
        request,
        "catalog/home.html",
        {"cameras": cameras, "reviews": reviews},
    )


def camera_list(request):
    cameras = Camera.objects.filter(is_active=True).prefetch_related("rates")
    query = request.GET.get("q", "").strip()
    brand = request.GET.get("brand", "").strip()
    order = request.GET.get("order", "recommended")

    if query:
        cameras = cameras.filter(Q(name__icontains=query) | Q(brand__icontains=query))
    if brand in Camera.Brand.values:
        cameras = cameras.filter(brand=brand)

    if order == "price":
        cameras = cameras.annotate(
            min_rate=Min(
                "rates__amount",
                filter=Q(rates__is_active=True),
            )
        ).order_by(
            "min_rate", "name"
        )
    else:
        cameras = cameras.order_by("brand", "name")

    return render(
        request,
        "catalog/list.html",
        {
            "cameras": cameras,
            "query": query,
            "selected_brand": brand,
            "selected_order": order,
            "brands": Camera.Brand.choices,
        },
    )


def camera_detail(request, slug):
    camera = get_object_or_404(
        Camera.objects.prefetch_related("rates"),
        slug=slug,
        is_active=True,
    )
    reviews = Feedback.objects.filter(
        camera=camera,
        is_published=True,
    ).select_related("user")
    return render(
        request,
        "catalog/detail.html",
        {"camera": camera, "reviews": reviews},
    )


def policies(request):
    return render(request, "catalog/policies.html")

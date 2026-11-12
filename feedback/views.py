
import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from catalog.models import Camera
from rentals.models import RentalOrder

from .forms import FeedbackForm
from .models import Feedback


# DỮ LIỆU PHẢN HỒI CÔNG KHAI
def _feedback_context(request, camera=None):
    entries = Feedback.objects.filter(
        is_published=True
    ).select_related("user", "camera")

    if camera is not None:
        entries = entries.filter(camera=camera)

    summary = entries.aggregate(
        review_count=Count("id"),
        average_rating=Avg("rating"),
    )

    cameras = Camera.objects.filter(
        is_active=True
    ).annotate(
        published_feedback_count=Count(
            "feedback_entries",
            filter=Q(
                feedback_entries__is_published=True
            ),
        )
    )

    return render(
        request,
        "feedback/list.html",
        {
            "entries": entries,
            "cameras": cameras,
            "selected_camera": camera,
            **summary,
        },
    )


# XEM TẤT CẢ PHẢN HỒI
def feedback_list(request):
    return _feedback_context(request)


# XEM PHẢN HỒI TỪNG MÁY
def feedback_camera(request, slug):
    camera = get_object_or_404(
        Camera,
        slug=slug,
        is_active=True,
    )

    return _feedback_context(request, camera=camera)


# KHÁCH GỬI PHẢN HỒI
@login_required
@require_http_methods(["GET", "POST"])
def feedback_create(request, order_id):
    order = get_object_or_404(
        RentalOrder.objects.select_related("camera"),
        pk=order_id,
        user=request.user,
        status=RentalOrder.Status.RETURNED,
    )

    if Feedback.objects.filter(order=order).exists():
        messages.info(
            request,
            "Đơn thuê này đã có phản hồi.",
        )
        return redirect("rentals:detail", pk=order.pk)

    form = FeedbackForm(
        request.POST or None,
        request.FILES or None,
    )

    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)

        entry.user = request.user
        entry.order = order
        entry.camera = order.camera

        try:
            entry.full_clean()

            with transaction.atomic():
                entry.save()

        except ValidationError as error:
            form.add_error(None, error)

        except IntegrityError:
            form.add_error(
                None,
                "Đơn thuê này đã có phản hồi.",
            )

        else:
            messages.success(
                request,
                "Phản hồi đã được gửi và đang chờ cửa hàng duyệt.",
            )
            return redirect("rentals:detail", pk=order.pk)

    return render(
        request,
        "feedback/form.html",
        {
            "form": form,
            "order": order,
        },
    )


# BẢO VỆ ẢNH PHẢN HỒI
def feedback_photo(request, pk):
    entry = get_object_or_404(Feedback, pk=pk)

    allowed_owner = (
        request.user.is_authenticated
        and request.user.pk == entry.user_id
    )

    allowed_staff = (
        request.user.is_authenticated
        and request.user.is_staff
        and request.user.has_perm("feedback.view_feedback")
    )

    if not entry.photo or not (
        entry.is_published
        or allowed_owner
        or allowed_staff
    ):
        raise Http404

    try:
        file = entry.photo.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404

    content_type = (
        mimetypes.guess_type(entry.photo.name)[0]
        or "application/octet-stream"
    )

    response = FileResponse(
        file,
        content_type=content_type,
    )

    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"

    return response

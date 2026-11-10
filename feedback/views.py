import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from rentals.models import RentalOrder
from catalog.models import Camera
from .forms import FeedbackForm
from .models import Feedback


def _feedback_context(request, *, camera=None):
    entries = Feedback.objects.filter(is_published=True).select_related("user", "camera")
    if camera is not None:
        entries = entries.filter(camera=camera)
    summary = entries.aggregate(
        review_count=Count("id"),
        average_rating=Avg("rating"),
    )
    cameras = Camera.objects.filter(is_active=True).annotate(
        published_feedback_count=Count(
            "feedback_entries",
            filter=Q(feedback_entries__is_published=True),
        )
    )
    return render(
        "feedback/list.html",
        {
            "entries": entries,
            "cameras": cameras,
            "selected_camera": camera,
            **summary,
        },
    )


def feedback_list(request):
    return _feedback_context(request)


def feedback_camera(request, slug):
    camera = get_object_or_404(Camera, slug=slug, is_active=True)
    return _feedback_context(request, camera=camera)


@login_required
def feedback_create(request, order_id):
    order = get_object_or_404(
        RentalOrder.objects.select_related("camera"),
        pk=order_id,
        user=request.user,
        status=RentalOrder.Status.RETURNED,
    )
    if Feedback.objects.filter(order=order).exists():
        messages.info(request, "Đơn thuê này đã có phản hồi.")
        return redirect("rentals:detail", pk=order.pk)

    form = FeedbackForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.order = order
        entry.camera = order.camera
        entry.full_clean()
        entry.save()
        messages.success(
            request,
            "Phản hồi đã được gửi và sẽ hiển thị sau khi cửa hàng duyệt.",
        )
        return redirect("feedback:list")
    return render(
        request,
        "feedback/form.html",
        {"form": form, "order": order},
    )


def feedback_photo(request, pk):
    entry = get_object_or_404(Feedback, pk=pk)
    if not entry.photo:
        raise Http404
    if not entry.is_published and not (
        request.user.is_authenticated
        and (request.user.pk == entry.user_id or request.user.is_staff)
    ):
        raise Http404

    content_type = mimetypes.guess_type(entry.photo.name)[0] or "application/octet-stream"
    response = FileResponse(entry.photo.open("rb"), content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response

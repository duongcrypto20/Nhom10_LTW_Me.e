
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from catalog.models import Camera
from customers.models import Notification

from .forms import FeedbackModerationForm
from .models import Feedback


# DANH SÁCH VÀ THỐNG KÊ PHẢN HỒI
@staff_member_required(login_url="customers:login")
@permission_required("feedback.view_feedback", raise_exception=True)
def feedback_manage(request):
    entries = Feedback.objects.select_related(
        "user",
        "camera",
        "order",
    )

    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "all")
    camera = request.GET.get("camera", "")
    rating = request.GET.get("rating", "")

    if query:
        entries = entries.filter(
            Q(content__icontains=query)
            | Q(camera__name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(order__order_code__icontains=query)
        )

    if status in {"published", "unpublished"}:
        entries = entries.filter(
            is_published=(status == "published")
        )

    if camera.isdecimal():
        entries = entries.filter(camera_id=int(camera))

    if rating in {"1", "2", "3", "4", "5"}:
        entries = entries.filter(rating=int(rating))

    statistics = Feedback.objects.aggregate(
        total=Count("id"),
        published=Count(
            "id",
            filter=Q(is_published=True),
        ),
        unpublished=Count(
            "id",
            filter=Q(is_published=False),
        ),
        average_rating=Avg(
            "rating",
            filter=Q(is_published=True),
        ),
    )

    page_obj = Paginator(
        entries.order_by("-created_at"),
        12,
    ).get_page(request.GET.get("page"))

    return render(
        request,
        "feedback/staff_list.html",
        {
            "entries": page_obj,
            "page_obj": page_obj,
            "statistics": statistics,
            "cameras": Camera.objects.order_by("name"),
            "query": query,
            "status_filter": status,
            "camera_filter": camera,
            "rating_filter": rating,
        },
    )


# DUYỆT VÀ TRẢ LỜI PHẢN HỒI
@staff_member_required(login_url="customers:login")
@permission_required("feedback.change_feedback", raise_exception=True)
@require_http_methods(["GET", "POST"])
def feedback_moderate(request, pk):
    entry = get_object_or_404(
        Feedback.objects.select_related(
            "user",
            "order",
            "camera",
        ),
        pk=pk,
    )

    form = FeedbackModerationForm(
        request.POST or None,
        instance=entry,
    )

    if request.method == "POST" and form.is_valid():
        old_published = entry.is_published
        old_reply = entry.shop_reply

        with transaction.atomic():
            form.save()

            if not old_published and entry.is_published:
                Notification.objects.create(
                    user=entry.user,
                    order_id=entry.order_id,
                    title="Phản hồi đã được duyệt",
                    message=(
                        "Đánh giá của bạn đã được hiển thị "
                        "trên website."
                    ),
                )

            if (
                entry.shop_reply.strip()
                and entry.shop_reply != old_reply
            ):
                Notification.objects.create(
                    user=entry.user,
                    order_id=entry.order_id,
                    title="Cửa hàng đã trả lời phản hồi",
                    message=entry.shop_reply,
                )

        messages.success(
            request,
            "Đã cập nhật trạng thái và trả lời phản hồi.",
        )
        return redirect("feedback:manage")

    return render(
        request,
        "feedback/staff_edit.html",
        {
            "entry": entry,
            "form": form,
        },
    )

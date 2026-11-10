from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("camera", "user", "rating", "is_published", "created_at")
    list_filter = ("is_published", "rating", "created_at")
    search_fields = ("camera__name", "user__email", "content")
    readonly_fields = ("user", "order", "camera", "rating", "content", "photo", "created_at")
    fieldsets = (
        ("Phản hồi khách hàng", {
            "fields": ("user", "order", "camera", "rating", "content", "photo", "created_at")
        }),
        ("Duyệt và trả lời", {"fields": ("is_published", "shop_reply")}),
    )

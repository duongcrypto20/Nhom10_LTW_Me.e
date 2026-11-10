from django.contrib import admin

from .models import Address, CustomerProfile, Notification


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "role")
    list_filter = ("role",)
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("label", "recipient", "district", "city", "is_default")
    search_fields = ("recipient", "phone", "street", "district", "city")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "created_at", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("title", "message", "user__email")

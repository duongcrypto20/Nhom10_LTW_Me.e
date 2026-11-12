
from django.urls import path
from .availability import staff_availability
from . import views

app_name = "rentals"

urlpatterns = [
    # ĐẶT THUÊ THIẾT BỊ
    path("dat/<slug:slug>/", views.booking, name="booking"),
    path("xac-nhan/", views.review, name="review"),
    path("thanh-cong/<int:pk>/", views.success, name="success"),

    # ĐƠN THUÊ KHÁCH HÀNG
    path("don-hang/", views.order_list, name="list"),
    path("don-hang/<int:pk>/", views.order_detail, name="detail"),

    # QUẢN LÝ ĐƠN THUÊ NHÂN VIÊN
    path("quan-ly/", views.staff_order_list, name="staff_orders"),
    path(
        "quan-ly/<int:pk>/",
        views.staff_order_detail,
        name="staff_order_detail",
    ),
    path(
        "quan-ly/<int:pk>/trang-thai/",
        views.staff_order_status,
        name="staff_order_status",
    ),
    path(
        "quan-ly/<int:pk>/tien-coc/",
        views.staff_order_deposit,
        name="staff_order_deposit",
    ),
    path("quan-ly/kiem-tra-may/", staff_availability, name="staff_availability"),
]

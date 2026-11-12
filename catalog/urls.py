
from django.urls import path

from . import views
from . import staff_views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("may-anh/", views.camera_list, name="list"),
    path("may-anh/<slug:slug>/", views.camera_detail, name="detail"),
    path("chinh-sach/", views.policies, name="policies"),

    # QUẢN LÝ MÁY ẢNH
    path(
        "quan-ly/may-anh/",
        staff_views.manage_cameras,
        name="manage_cameras",
    ),
    path(
        "quan-ly/may-anh/them/",
        staff_views.create_camera,
        name="create_camera",
    ),
    path(
        "quan-ly/may-anh/<int:pk>/sua/",
        staff_views.edit_camera,
        name="edit_camera",
    ),

    # QUẢN LÝ GÓI THUÊ
    path(
        "quan-ly/goi-thue/",
        staff_views.manage_rates,
        name="manage_rates",
    ),
    path(
        "quan-ly/goi-thue/them/",
        staff_views.create_rate,
        name="create_rate",
    ),
    path(
        "quan-ly/goi-thue/<int:pk>/sua/",
        staff_views.edit_rate,
        name="edit_rate",
    ),
]

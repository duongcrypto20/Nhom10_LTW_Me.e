from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("may-anh/", views.camera_list, name="list"),
    path("may-anh/<slug:slug>/", views.camera_detail, name="detail"),
    path("chinh-sach/", views.policies, name="policies"),
]

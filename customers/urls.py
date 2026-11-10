from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("quan-ly/", views.staff_dashboard, name="staff_dashboard"),
    path("dang-ky/", views.register, name="register"),
    path("dang-nhap/", views.login_view, name="login"),
    path("dang-xuat/", views.logout_view, name="logout"),
    path("", views.profile, name="profile"),
    path("dia-chi/", views.address_list, name="addresses"),
    path("dia-chi/tao/", views.address_create, name="address_create"),
    path("dia-chi/<int:pk>/mac-dinh/", views.address_default, name="address_default"),
    path("dia-chi/<int:pk>/xoa/", views.address_delete, name="address_delete"),
    path("thong-bao/", views.notification_list, name="notifications"),
    path("thong-bao/<int:pk>/doc/", views.notification_read, name="notification_read"),
]

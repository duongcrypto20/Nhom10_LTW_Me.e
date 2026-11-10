from django.urls import path

from . import views

app_name = "rentals"

urlpatterns = [
    path("dat/<slug:slug>/", views.booking, name="booking"),
    path("xac-nhan/", views.review, name="review"),
    path("thanh-cong/<int:pk>/", views.success, name="success"),
    path("don-hang/", views.order_list, name="list"),
    path("don-hang/<int:pk>/", views.order_detail, name="detail"),
]

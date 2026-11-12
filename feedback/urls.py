
from django.urls import path

from . import views
from . import staff_views

app_name = "feedback"

urlpatterns = [
    path("", views.feedback_list, name="list"),

    path(
        "may-anh/<slug:slug>/",
        views.feedback_camera,
        name="camera",
    ),

    path(
        "gui/<int:order_id>/",
        views.feedback_create,
        name="create",
    ),

    path(
        "anh/<int:pk>/",
        views.feedback_photo,
        name="photo",
    ),

    path(
        "quan-ly/",
        staff_views.feedback_manage,
        name="manage",
    ),

    path(
        "quan-ly/<int:pk>/",
        staff_views.feedback_moderate,
        name="moderate",
    ),
]

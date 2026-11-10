from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("", views.feedback_list, name="list"),
    path("may-anh/<slug:slug>/", views.feedback_camera, name="camera"),
    path("gui/<int:order_id>/", views.feedback_create, name="create"),
    path("anh/<int:pk>/", views.feedback_photo, name="photo"),
]

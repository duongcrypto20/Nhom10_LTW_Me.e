from django.urls import path

from . import views

urlpatterns = [
    path('dang-ky/', views.dang_ky, name='dang_ky'),
    path('dang-nhap/', views.dang_nhap, name='dang_nhap'),
    path('dang-xuat/', views.dang_xuat, name='dang_xuat'),
    path('tai-khoan/', views.tai_khoan, name='tai_khoan'),
    path('tai-khoan/doi-mat-khau/', views.doi_mat_khau, name='doi_mat_khau'),
    # Khu vực quản lý
    path('quan-ly/tai-khoan/', views.ql_tai_khoan, name='ql_tai_khoan'),
    path('quan-ly/tai-khoan/<int:pk>/vai-tro/', views.ql_doi_vai_tro, name='ql_doi_vai_tro'),
    path('quan-ly/tai-khoan/<int:pk>/khoa/', views.ql_khoa_tai_khoan, name='ql_khoa_tai_khoan'),
]

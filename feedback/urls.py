from django.urls import path

from . import views

urlpatterns = [
    path('danh-gia/', views.ds_danh_gia, name='ds_danh_gia'),
    path('feedback-cua-toi/', views.phan_hoi_cua_toi, name='phan_hoi_cua_toi'),
    path('danh-gia/gui/<int:don_pk>/', views.gui_danh_gia, name='gui_danh_gia'),
    # Khu vực quản lý
    path('quan-ly/phan-hoi/', views.ql_phan_hoi, name='ql_phan_hoi'),
    path('quan-ly/phan-hoi/<int:pk>/trang-thai/', views.ql_doi_trang_thai_phan_hoi,
         name='ql_doi_trang_thai_phan_hoi'),
    path('quan-ly/phan-hoi/<int:pk>/', views.ql_chi_tiet_phan_hoi, name='ql_chi_tiet_phan_hoi'),
    path('quan-ly/phan-hoi/<int:pk>/tra-loi/', views.ql_chi_tiet_phan_hoi, name='ql_tra_loi_phan_hoi'),
]

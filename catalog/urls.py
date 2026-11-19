from django.urls import path

from . import views

urlpatterns = [
    # Trang công khai
    path('', views.trang_chu, name='trang_chu'),
    path('may-anh/', views.ds_may_anh, name='ds_may_anh'),
    path('kiem-tra-may-trong/', views.kiem_tra_lich, name='kiem_tra_lich'),
    path('may-anh/<str:ma>/', views.chi_tiet_may_anh, name='chi_tiet_may_anh'),
    path('may-anh/<str:ma>/kiem-tra-trong/', views.kiem_tra_may_trong, name='kiem_tra_may_trong'),
    path('goi-thue/', views.goi_thue, name='goi_thue'),
    path('quy-dinh/', views.quy_dinh, name='quy_dinh'),
    # Khu vực quản lý
    path('quan-ly/thiet-bi/', views.ql_thiet_bi, name='ql_thiet_bi'),
    path('quan-ly/thiet-bi/them/', views.ql_them_thiet_bi, name='ql_them_thiet_bi'),
    path('quan-ly/thiet-bi/<int:pk>/', views.ql_sua_thiet_bi, name='ql_sua_thiet_bi'),
    path('quan-ly/thiet-bi/<int:pk>/them-may/', views.ql_them_may, name='ql_them_may'),
    path('quan-ly/may/<int:pk>/tinh-trang/', views.ql_doi_tinh_trang_may, name='ql_doi_tinh_trang_may'),
    path('quan-ly/dich-vu/', views.ql_dich_vu, name='ql_dich_vu'),
    path('quan-ly/dich-vu/them-goi/', views.ql_them_goi, name='ql_them_goi'),
    path('quan-ly/dich-vu/goi/<int:pk>/', views.ql_sua_goi, name='ql_sua_goi'),
    path('quan-ly/ma-giam-gia/', views.ql_ma_giam_gia, name='ql_ma_giam_gia'),
    path('quan-ly/ma-giam-gia/them/', views.ql_them_ma_giam_gia, name='ql_them_ma_giam_gia'),
    path('quan-ly/ma-giam-gia/<int:pk>/', views.ql_sua_ma_giam_gia, name='ql_sua_ma_giam_gia'),
    path('quan-ly/danh-muc/', views.ql_danh_muc, name='ql_danh_muc'),
]

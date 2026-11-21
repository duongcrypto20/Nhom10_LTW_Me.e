"""Đường dẫn của app rentals (đặt thuê và tiền cọc)."""
from django.urls import path

from . import views

urlpatterns = [
    # ----- Khách hàng: đặt thuê và đặt cọc -----
    path('dat-thue/xac-nhan/', views.xac_nhan_dat_thue, name='xac_nhan_dat_thue'),
    path('dat-thue/<str:ma>/', views.dat_thue, name='dat_thue'),
    path('cua-toi/', views.trang_cua_toi, name='trang_cua_toi'),
    path('don-cua-toi/', views.don_cua_toi, name='don_cua_toi'),
    path('don-cua-toi/<int:pk>/', views.chi_tiet_don, name='chi_tiet_don'),
    path('don-cua-toi/<int:pk>/sua/', views.sua_don, name='sua_don'),
    path('don-cua-toi/<int:pk>/huy/', views.huy_don, name='huy_don'),
    path('don-cua-toi/<int:pk>/dat-coc/', views.dat_coc, name='dat_coc'),
    path('thong-bao/', views.thong_bao, name='thong_bao'),

    # ----- Nhân viên: xử lý yêu cầu thuê -----
    path('quan-ly/', views.ql_tong_quan, name='ql_tong_quan'),
    path('quan-ly/yeu-cau/', views.ql_yeu_cau, name='ql_yeu_cau'),
    path('quan-ly/yeu-cau/<int:pk>/', views.ql_xu_ly_yeu_cau, name='ql_xu_ly_yeu_cau'),
    path('quan-ly/don/<int:pk>/', views.ql_chi_tiet_don, name='ql_chi_tiet_don'),
    path('quan-ly/don/<int:pk>/huy/', views.ql_huy_don, name='ql_huy_don'),
    path('quan-ly/don/<int:pk>/doi-may/', views.ql_phan_bo_lai, name='ql_phan_bo_lai'),

    # ----- Nhân viên: tiền cọc -----
    path('quan-ly/tien-coc/', views.ql_tien_coc, name='ql_tien_coc'),
    path('quan-ly/tien-coc/<int:pk>/thu-coc/', views.ql_thu_coc, name='ql_thu_coc'),
    path('quan-ly/tien-coc/<int:pk>/hoan-coc/', views.ql_hoan_coc, name='ql_hoan_coc'),

    # ----- Lịch máy và báo cáo -----
    path('quan-ly/lich/', views.ql_lich, name='ql_lich'),
    path('quan-ly/bao-cao/', views.ql_bao_cao, name='ql_bao_cao'),

    # ----- Sự cố máy -----
    path('quan-ly/su-co/', views.ql_su_co, name='ql_su_co'),
    path('quan-ly/su-co/<int:pk>/', views.ql_chi_tiet_su_co, name='ql_chi_tiet_su_co'),
    path('quan-ly/su-co/ghi-nhan/don/<int:pk>/', views.ql_ghi_nhan_su_co, name='ql_ghi_nhan_su_co'),
]

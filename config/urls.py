from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('catalog.urls')),
    path('', include('rentals.urls')),
    path('', include('feedback.urls')),
]

# Khi chạy thử (DEBUG) cho phép Django phục vụ ảnh tải lên
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

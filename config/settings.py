"""
Cấu hình dự án me.e_digitalcam (website cho thuê máy ảnh).
Dự án học tập nên dùng SQLite và bật DEBUG.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-du-an-hoc-tap-mee-digitalcam'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Các app của dự án
    'accounts',   # tài khoản và phân quyền (UC-6)
    'catalog',    # thiết bị, gói thuê, giá thuê (UC-2, UC-3)
    'rentals',    # đặt thuê và tiền cọc (UC-1, tiền cọc gộp từ UC-5)
    'feedback',   # phản hồi, đánh giá (UC-4)
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'rentals.context_processors.thong_bao',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Dùng model User riêng để có thêm trường vai trò
AUTH_USER_MODEL = 'accounts.User'

# Dự án demo nên không bật kiểm tra độ mạnh mật khẩu
AUTH_PASSWORD_VALIDATORS = []

LOGIN_URL = 'dang_nhap'

LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Ảnh do người dùng tải lên (ảnh thiết bị, ảnh feedback)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Thông tin cửa hàng dùng chung trong giao diện
CUA_HANG = {
    'ten': 'me.e_digitalcam',
    'dia_chi': '75 Lê Thị Hồng Gấm, Đà Nẵng',
    'zalo': '0917 999 277 / 0834 020 466',
}

# Thông tin trong ảnh ngân hàng được cung cấp; có thể đổi bằng biến môi trường.
THANH_TOAN = {
    'ngan_hang': os.environ.get('MEE_BANK_ID', 'MB'),
    'so_tai_khoan': os.environ.get('MEE_BANK_ACCOUNT', '0357594008'),
    'chu_tai_khoan': os.environ.get('MEE_BANK_HOLDER', 'NGO QUYNH DUONG'),
    'anh_qr': os.environ.get('MEE_BANK_QR_IMAGE', 'img/qr-coc-lich.jpg'),
}

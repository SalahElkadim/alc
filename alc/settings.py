from datetime import timedelta
from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY="django-insecure-3#-m1uyln4jei7me&3=*+ued3w403@(72wxzg#$2@o_s@so_7l"
# JWT

# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = [
    "alc-production-5d34.up.railway.app  " , 
    "https://alc-production-5d34.up.railway.app",
    "localhost",
    "127.0.0.1",
]
CSRF_TRUSTED_ORIGINS = [
    "https://alc-production-5d34.up.railway.app",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'users',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'questions',
    'exam',
    'payments',


]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
# إعدادات JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":1  ,
    "REFRESH_TOKEN_LIFETIME":7 ,
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.SingleDeviceMiddleware',  # أضف هنا
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

]
CORS_ALLOWED_ORIGINS = [
    "https://alc-production-5d34.up.railway.app",
    "http://localhost:3000",   
]
AUTH_USER_MODEL = 'users.CustomUser'
ROOT_URLCONF = 'alc.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'alc.wsgi.application'

#CORS_ALLOW_ALL_ORIGINS = True  # للتطوير فقط
CORS_ALLOW_CREDENTIALS = True




# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.parse(
"postgresql://postgres:tHTpzmhrKmjpBODZffagOQKAVwzBYLBE@hopper.proxy.rlwy.net:17588/railway",
        conn_max_age=600,
        engine='django.db.backends.postgresql_psycopg2'
    )
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
#FRONTEND_URL = 'http://localhost:3000'  # أو الـ URL بتاع الـ frontend

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "salah.mohamed.elkadim@gmail.com"
EMAIL_HOST_USER = "salah.mohamed.elkadim@gmail.com"
EMAIL_HOST_PASSWORD = "fqzd njeb fffg sact"



SESSION_EXPIRE_SECONDS = 24 * 60 * 60  # 24 ساعة
from django.core.management import BaseCommand

class Command(BaseCommand):
    """Management command لتنظيف الجلسات المنتهية"""
    help = 'Clean expired sessions'

    def handle(self, *args, **options):
        from users.models import UserSession
        from django.utils import timezone
        from datetime import timedelta
        
        expired_sessions = UserSession.objects.filter(
            last_activity__lt=timezone.now() - timedelta(hours=24)
        )
        count = expired_sessions.count()
        expired_sessions.delete()
        
        self.stdout.write(f'Cleaned {count} expired sessions')


MOYASAR_SECRET_KEY = "sk_live_Kv99pG1WCswpafrzbfpGH9E1w1YucyixxfcnKDLM"
MOYASAR_PUBLISHABLE_KEY = "pk_live_fKVM1h6efFnnvHcCz34HWaRFUMwuUBuXBs1qTYxk"
MOYASAR_BASE_URL = "https://api.moyasar.com/v1/"
DEBUG=True
#DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

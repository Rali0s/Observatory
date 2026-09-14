"""Local defaults; production deliberately requires explicit secrets and PostgreSQL."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY is required in production.')
    SECRET_KEY = 'local-development-only-observatory-key-not-for-hosting'
ALLOWED_HOSTS = [s.strip() for s in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if s.strip()]
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if s.strip()]
# Railway updates this exact hostname when a generated domain is renamed.
railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
if railway_domain and all(c.isalnum() or c in '.-' for c in railway_domain):
    ALLOWED_HOSTS.append(railway_domain)
    CSRF_TRUSTED_ORIGINS.append('https://' + railway_domain)
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'studio',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'observatory.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'observatory.wsgi.application'
ASGI_APPLICATION = 'observatory.asgi.application'
if os.getenv('POSTGRES_DB'):
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ['POSTGRES_DB'],
        'USER': os.environ['POSTGRES_USER'], 'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'), 'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60, 'OPTIONS': {'sslmode': os.getenv('POSTGRES_SSLMODE', 'require')},
    }}
else:
    if not DEBUG:
        raise ImproperlyConfigured('Configure PostgreSQL before running in production.')
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'library'
LOGOUT_REDIRECT_URL = 'login'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
# Local alpha: synchronous analysis is intentionally bounded until a worker exists.
OBSERVATORY_MAX_WORDS = 20000
STORAGE_QUOTA_BYTES = int(os.getenv('STORAGE_QUOTA_BYTES', '100000000'))
SEMANTIC_MODEL = os.getenv('OPENAI_NARRATIVE_MODEL', '')
SEMANTIC_ENABLED = os.getenv('SEMANTIC_ENABLED', '0') == '1'
BITCOIN_ESPLORA_URL = os.getenv('BITCOIN_ESPLORA_URL', 'https://blockstream.info/api')
BLOCK_MAX_AGE_SECONDS = 300
BTCPAY_URL = os.getenv('BTCPAY_URL', '')
BTCPAY_STORE_ID = os.getenv('BTCPAY_STORE_ID', '')
BTCPAY_API_KEY = os.getenv('BTCPAY_API_KEY', '')
if os.getenv('REDIS_URL'):
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': os.environ['REDIS_URL']}}
if os.getenv('TRUST_PROXY_HTTPS') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REDIRECT_EXEMPT = [r'^health/$']

DIRECT_BITCOIN_ENABLED = os.getenv('DIRECT_BITCOIN_ENABLED', '0') == '1'

# An operator-controlled mainnet ord server, with JSON API and sat indexing enabled.
ORDINAL_INDEX_URL = os.getenv('ORDINAL_INDEX_URL', '')

STRIPE_ENABLED = os.getenv('STRIPE_ENABLED', '0') == '1'
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'https://' + railway_domain if railway_domain else 'http://127.0.0.1:8000').rstrip('/')

# Enable only after staging wallet/transaction verification with a trusted ord index.
ORDINAL_TRADING_ENABLED = os.getenv('ORDINAL_TRADING_ENABLED', '0') == '1'
ORDINAL_MAX_PRICE_SATS = 100000000
ORDINAL_MAX_FEE_SATS = 100000

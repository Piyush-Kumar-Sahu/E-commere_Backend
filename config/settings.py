import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse, urlunparse
import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'modiecommers-insecure-key-for-development-only-change-me')

# Environment and Debug Mode Configuration
# Production is detected via Render platform variables or explicit environment configuration.
IS_RENDER = os.getenv('RENDER') == 'true' or bool(os.getenv('RENDER_EXTERNAL_HOSTNAME'))
IS_PRODUCTION = (
    IS_RENDER or
    os.getenv('ENVIRONMENT', '').strip().lower() in ('production', 'prod') or
    os.getenv('DJANGO_ENV', '').strip().lower() in ('production', 'prod')
)

# In production, DEBUG must always be False for security.
# In local development, DJANGO_DEBUG defaults to True unless explicitly disabled.
if IS_PRODUCTION:
    DEBUG = False
else:
    DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

# Allowed Hosts Configuration
# Local development hosts, test runner, and the production Render domain are preserved.
# Additional hosts can be supplied via the DJANGO_ALLOWED_HOSTS environment variable.
DEFAULT_ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '[::1]',
    'testserver',
    'e-commere-backend.onrender.com',
]

render_external_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname and render_external_hostname not in DEFAULT_ALLOWED_HOSTS:
    DEFAULT_ALLOWED_HOSTS.append(render_external_hostname)

allowed_hosts_raw = os.getenv('DJANGO_ALLOWED_HOSTS', '')
parsed_env_hosts = [h.strip() for h in allowed_hosts_raw.split(',') if h.strip()]

# Build safe, deduplicated ALLOWED_HOSTS list while strictly forbidding wildcard '*'
ALLOWED_HOSTS = []
for host in DEFAULT_ALLOWED_HOSTS + parsed_env_hosts:
    if host and host != '*' and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# Health check configuration (default True, can be disabled for zero-overhead liveness probes)
HEALTH_CHECK_INCLUDE_DB = os.getenv('HEALTH_CHECK_INCLUDE_DB', 'True').lower() in ('true', '1', 'yes')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party packages
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',

    # Local apps
    'apps.core.apps.CoreConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.catalogue.apps.CatalogueConfig',
    'apps.cart.apps.CartConfig',
    'apps.orders.apps.OrdersConfig',
    'apps.reviews.apps.ReviewsConfig',
    'apps.promotions.apps.PromotionsConfig',
    'apps.admin_ops.apps.AdminOpsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database Configuration (Supabase PostgreSQL via DATABASE_URL with SSL)
raw_database_url = os.getenv('DATABASE_URL')
if not raw_database_url:
    raise ValueError("DATABASE_URL environment variable is not configured. Please supply a valid Supabase PostgreSQL connection URL in .env.")

# Supabase direct endpoints (db.<project-ref>.supabase.co) only resolve to IPv6, which is unreachable on Render's network.
# If a direct endpoint is supplied, route through the Supabase Session Pooler (port 5432, IPv4 compatible).
parsed_db = urlparse(raw_database_url)
if parsed_db.hostname and parsed_db.hostname.startswith('db.') and parsed_db.hostname.endswith('.supabase.co'):
    ref = parsed_db.hostname.split('.')[1]
    pooler_host = os.getenv('SUPABASE_POOLER_HOST', 'aws-0-ap-south-1.pooler.supabase.com')
    user = parsed_db.username or 'postgres'
    if not user.startswith('postgres.'):
        user = f"postgres.{ref}"
    netloc = f"{user}:{parsed_db.password}@{pooler_host}:{parsed_db.port or 5432}"
    DATABASE_URL = urlunparse((parsed_db.scheme, netloc, parsed_db.path, parsed_db.params, parsed_db.query, parsed_db.fragment))
else:
    DATABASE_URL = raw_database_url

DATABASES = {
    'default': dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv('DATABASE_CONN_MAX_AGE', '600')),
        conn_health_checks=True,
        ssl_require=True,
    )
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (Product uploads, banners)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# Simple JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=4),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

from corsheaders.defaults import default_headers

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-cart-session',
]

default_cors_origins = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'https://modi-e-commerce.onrender.com',
]

cors_raw = os.getenv('CORS_ALLOWED_ORIGINS', '')
parsed_cors_origins = [c.strip() for c in cors_raw.split(',') if c.strip()]

CORS_ALLOWED_ORIGINS = []
for origin in default_cors_origins + parsed_cors_origins:
    if origin and origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(origin)

default_csrf_trusted = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'https://e-commere-backend.onrender.com',
    'https://modi-e-commerce.onrender.com',
]
if render_external_hostname and f"https://{render_external_hostname}" not in default_csrf_trusted:
    default_csrf_trusted.append(f"https://{render_external_hostname}")

csrf_raw = os.getenv('CSRF_TRUSTED_ORIGINS', '')
parsed_csrf_origins = [c.strip() for c in csrf_raw.split(',') if c.strip()]

CSRF_TRUSTED_ORIGINS = []
for origin in default_csrf_trusted + parsed_csrf_origins:
    if origin and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

# Email Configuration (Gmail SMTP with environment variables)
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if (DEBUG and (not os.getenv('EMAIL_HOST_USER') or os.getenv('EMAIL_HOST_USER') == 'your-gmail-address@gmail.com')) else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@modiecommers.com')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', 30))

# Password Reset Token Timeout (1 hour)
PASSWORD_RESET_TIMEOUT = int(os.getenv('PASSWORD_RESET_TIMEOUT', 3600))

# OTP Expiry & Rate Limiting Configuration
EMAIL_OTP_EXPIRY_SECONDS = int(os.getenv('EMAIL_OTP_EXPIRY_SECONDS', 600))  # 10 minutes
EMAIL_OTP_COOLDOWN_SECONDS = int(os.getenv('EMAIL_OTP_COOLDOWN_SECONDS', 60))  # 60 seconds
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://modi-e-commerce.onrender.com' if IS_PRODUCTION else 'http://localhost:5173').rstrip('/')


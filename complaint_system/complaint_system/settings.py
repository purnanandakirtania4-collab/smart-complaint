from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables from:
# complaint_system/.env
load_dotenv(BASE_DIR / ".env")


# =========================================================
# BASIC SETTINGS
# =========================================================

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-this-in-production",
)

_running_on_railway = any(
    os.environ.get(name)
    for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_NAME",
        "RAILWAY_PROJECT_ID",
    )
)

_default_debug = "False" if _running_on_railway else "True"

DEBUG = os.environ.get(
    "DEBUG",
    _default_debug,
).lower() == "true"

ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "https://smart-complaint-production.up.railway.app",
]

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Keep this False because the Android WebView bridge reads csrftoken for FCM POSTs.
CSRF_COOKIE_HTTPONLY = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True


# =========================================================
# INSTALLED APPS
# =========================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "complaints",
]


# =========================================================
# LOGIN / LOGOUT
# =========================================================

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL / WSGI
# =========================================================

ROOT_URLCONF = "complaint_system.urls"

WSGI_APPLICATION = "complaint_system.wsgi.application"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =========================================================
# DATABASE
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get(
            "MYSQL_DATABASE",
            "complaint_db",
        ),
        "USER": os.environ.get(
            "MYSQLUSER",
            "root",
        ),
        "PASSWORD": os.environ.get(
            "MYSQLPASSWORD",
            "",
        ),
        "HOST": os.environ.get(
            "MYSQLHOST",
            "127.0.0.1",
        ),
        "PORT": os.environ.get(
            "MYSQLPORT",
            "3306",
        ),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# LANGUAGE / TIMEZONE
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC / MEDIA
# =========================================================

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MEDIA_URL = "/media/"

# On Railway, mount a persistent Volume at /app/media and set
# MEDIA_ROOT=/app/media. Local development continues using BASE_DIR/media.
MEDIA_ROOT = Path(
    os.environ.get(
        "MEDIA_ROOT",
        str(BASE_DIR / "media"),
    )
)


# =========================================================
# EMAIL / FORGOT PASSWORD
# =========================================================
#
# LOCAL TESTING:
# If EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are empty,
# Django prints the password-reset email and reset URL
# directly in the runserver terminal.
#
# PRODUCTION:
# Add EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to Railway
# environment variables.
#
# For Gmail, EMAIL_HOST_PASSWORD should be a Google
# App Password, NOT the normal Gmail password.
# =========================================================

EMAIL_HOST = os.environ.get(
    "EMAIL_HOST",
    "smtp.gmail.com",
)

EMAIL_PORT = int(
    os.environ.get(
        "EMAIL_PORT",
        "587",
    )
)

EMAIL_USE_TLS = os.environ.get(
    "EMAIL_USE_TLS",
    "True",
).lower() == "true"

EMAIL_HOST_USER = os.environ.get(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = os.environ.get(
    "EMAIL_HOST_PASSWORD",
    "",
)

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "Smart Complaint <noreply@smartcomplaint.local>",
)

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Password reset link expires after 1 hour.
PASSWORD_RESET_TIMEOUT = 60 * 60


# =========================================================
# RAZORPAY
# =========================================================

RAZORPAY_KEY_ID = os.environ.get(
    "RAZORPAY_KEY_ID",
    "",
)

RAZORPAY_KEY_SECRET = os.environ.get(
    "RAZORPAY_KEY_SECRET",
    "",
)

RAZORPAY_WORKER_PLAN_ID = os.environ.get(
    "RAZORPAY_WORKER_PLAN_ID",
    "",
)

RAZORPAY_WORKER_PLAN_4M_ID = os.environ.get(
    "RAZORPAY_WORKER_PLAN_4M_ID",
    "",
)

RAZORPAY_WORKER_PLAN_YEARLY_ID = os.environ.get(
    "RAZORPAY_WORKER_PLAN_YEARLY_ID",
    "",
)

RAZORPAY_WEBHOOK_SECRET = os.environ.get(
    "RAZORPAY_WEBHOOK_SECRET",
    "",
)
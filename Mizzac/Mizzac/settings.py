"""Django settings for Mizzac.

All deployment-sensitive values come from the environment. SQLite remains the
development default; PostgreSQL can be selected without changing application
code.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name, default=False):
    """Read a strict boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} doit être un booléen explicite.")


def env_int(name, default):
    """Read an integer environment variable with a clear configuration error."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} doit être un entier.") from exc


def env_list(name, default=()):
    """Read a comma-separated environment variable."""
    value = os.getenv(name)
    if value is None:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY est obligatoire. Copiez .env.example vers .env pour le développement."
    )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=("localhost", "127.0.0.1") if DEBUG else (),
)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "Core",
    "GameBoard",
    "FundBoard",
    "DrunkBoard",
    "DashBoard",
    "ToolBoard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "Core.middleware.BrowserSecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "Mizzac.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "Mizzac.wsgi.application"

DATABASE_ENGINE = os.getenv("DJANGO_DB_ENGINE", "django.db.backends.sqlite3")
DATABASE_NAME = os.getenv("DJANGO_DB_NAME")
if DATABASE_ENGINE == "django.db.backends.sqlite3":
    DATABASE_NAME = DATABASE_NAME or "db.sqlite3"
    if DATABASE_NAME == ":memory:":
        database_name = DATABASE_NAME
    else:
        database_name = Path(DATABASE_NAME)
        if not database_name.is_absolute():
            database_name = BASE_DIR / database_name
    DATABASES = {
        "default": {
            "ENGINE": DATABASE_ENGINE,
            "NAME": database_name,
        }
    }
elif DATABASE_ENGINE in {
    "django.db.backends.postgresql",
    "django.db.backends.postgresql_psycopg2",
}:
    if not DATABASE_NAME:
        raise ImproperlyConfigured("DJANGO_DB_NAME est obligatoire pour PostgreSQL.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DATABASE_NAME,
            "USER": os.getenv("DJANGO_DB_USER", ""),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "localhost"),
            "PORT": os.getenv("DJANGO_DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DJANGO_DB_CONN_MAX_AGE", 60),
        }
    }
else:
    raise ImproperlyConfigured(f"Moteur de base non pris en charge : {DATABASE_ENGINE}")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Europe/Paris")
USE_I18N = True
USE_TZ = True

FUND_BOARD_EQUITY_PROVIDER = os.getenv("FUND_BOARD_EQUITY_PROVIDER", "yahoo")
FUND_BOARD_CRYPTO_PROVIDER = os.getenv("FUND_BOARD_CRYPTO_PROVIDER", "coingecko")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
FUND_BOARD_TRADE_REPUBLIC_LIVE_ENABLED = env_bool(
    "FUND_BOARD_TRADE_REPUBLIC_LIVE_ENABLED",
    False,
)
FUNDBOARD_SYNC_INTERVAL_MINUTES = env_int("FUNDBOARD_SYNC_INTERVAL_MINUTES", 360)
FUNDBOARD_SYNC_RETRY_MINUTES = env_int("FUNDBOARD_SYNC_RETRY_MINUTES", 30)
FUNDBOARD_MAINTENANCE_STALE_MINUTES = env_int(
    "FUNDBOARD_MAINTENANCE_STALE_MINUTES",
    120,
)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:dashboard"
LOGOUT_REDIRECT_URL = "dashboard:login"

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
if env_bool("DJANGO_USE_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").strip().upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ImproperlyConfigured("DJANGO_LOG_LEVEL est invalide.")
LOG_JSON = env_bool("DJANGO_LOG_JSON", False)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {"()": "Core.observability.SecretRedactionFilter"},
    },
    "formatters": {
        "plain": {
            "()": "Core.observability.RedactingFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "json": {"()": "Core.observability.JsonLogFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets"],
            "formatter": "json" if LOG_JSON else "plain",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "FundBoard": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

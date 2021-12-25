"""Django settings, all overridable through environment variables (see ../.env.example)."""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent


def _load_env_file(path: Path) -> None:
    """Read KEY=VALUE lines into os.environ without overriding real env vars."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file(REPO_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY (or DJANGO_DEBUG=1 for local development).")

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "jobs",
]

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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# PostgreSQL only: search uses tsvector/websearch_to_tsquery and tags are a text[] array.
# DATABASE_URL=embedded starts a private server from the pgserver wheel (no Docker needed).
_database_url = env("DATABASE_URL", "postgres://jobs:jobs@localhost:5432/jobs")
if _database_url == "embedded":
    from .embedded import embedded_url

    _database_url = embedded_url(env("EMBEDDED_DB_DIR", str(REPO_DIR / ".data" / "pgdata")))
DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=60, conn_health_checks=True)}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": env("API_RATE_LIMIT", "240/min")},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        # pgserver logs every pg_ctl call at INFO, including from atexit after streams close.
        "pgserver": {"level": "WARNING"},
    },
}

# --- aggregator settings --------------------------------------------------------

# Shared secret the scrapers send as "Authorization: Token <value>". Empty disables ingest.
INGEST_TOKEN = env("INGEST_TOKEN")

# The scraper skips detail pages for jobs whose listing hasn't changed, but only
# if the detail was fetched within this window, so salary edits still get picked up.
DETAIL_MAX_AGE_HOURS = int(env("DETAIL_MAX_AGE_HOURS", "24"))

# A complete run closes the source's jobs it didn't see, unless that would close
# more than this share of them (a sign the scraper broke, not that jobs vanished).
MAX_CLOSE_FRACTION = float(env("MAX_CLOSE_FRACTION", "0.5"))

# Rough conversion rates for the "minimum salary" filter. Static on purpose: the
# filter is a coarse sieve, not payroll. Unknown currencies are left out of it.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "CHF": 1.13, "AUD": 0.66, "PLN": 0.25, "SEK": 0.095}

def render_template(data=None):
    if data is None:
        return None
    return data

def run_migration(data=None):
    if data is None:
        return None
    return data

def render_template(data=None):
    if data is None:
        return None
    return data
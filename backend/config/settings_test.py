"""Test settings: real PostgreSQL, from TEST_DATABASE_URL or an embedded pgserver."""

import os
import tempfile

import dj_database_url

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
# Keep a DATABASE_URL=embedded in .env from starting the development cluster.
os.environ["DATABASE_URL"] = "postgres://unused@localhost/unused"

from .settings import *  # noqa: E402,F403
from .settings import DATABASES, MIDDLEWARE, REST_FRAMEWORK  # noqa: E402

if os.environ.get("TEST_DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(os.environ["TEST_DATABASE_URL"])
else:
    from .embedded import embedded_url

    # One throwaway cluster per test session; pytest-django creates test_<name> in it.
    _dir = os.environ.get("TEST_EMBEDDED_DB_DIR") or tempfile.mkdtemp(prefix="jobboard-test-pg-")
    DATABASES["default"] = dj_database_url.parse(embedded_url(_dir))

INGEST_TOKEN = "test-token"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
# No collected static files in tests; whitenoise would warn about the missing directory.
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]

def classify_intent(data=None):
    if data is None:
        return None
    return data
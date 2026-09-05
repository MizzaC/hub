"""Hermetic settings used by the automated test suite."""

import os

os.environ["DJANGO_SECRET_KEY"] = (
    "tests-only-key-with-more-than-fifty-characters-never-use-in-production"
)
os.environ["DJANGO_DEBUG"] = "False"
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"
os.environ["DJANGO_DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DJANGO_DB_NAME"] = ":memory:"
os.environ["DJANGO_SESSION_COOKIE_SECURE"] = "False"
os.environ["DJANGO_CSRF_COOKIE_SECURE"] = "False"

from .settings import *  # noqa: E402,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

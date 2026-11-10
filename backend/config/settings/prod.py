"""Production settings for an HTTPS reverse proxy with a private app port."""

from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
REFRESH_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Raise only after real HTTPS, domain ownership and subdomain policy are verified.
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=0)
if not ALLOWED_HOSTS or not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("Production host and origin allowlists are required")
if "*" in ALLOWED_HOSTS or any("*" in origin for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("Wildcard hosts and origins are forbidden in production")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("replace-"):
    raise ImproperlyConfigured("A unique production DJANGO_SECRET_KEY is required")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production requires PostgreSQL")
if not REDIS_URL:
    raise ImproperlyConfigured("Production requires Redis")
if not PUBLIC_WEB_ORIGIN.startswith("https://"):
    raise ImproperlyConfigured("PUBLIC_WEB_ORIGIN must use HTTPS in production")
if PUBLIC_WEB_ORIGIN not in CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("PUBLIC_WEB_ORIGIN must be in the CORS allowlist")
if any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("Production CORS origins must use HTTPS")
if IMPORT_INFERENCE_URL:
    inference = urlsplit(IMPORT_INFERENCE_URL)
    if inference.scheme != "https" and not (
        inference.scheme == "http" and inference.hostname and "." not in inference.hostname
    ):
        raise ImproperlyConfigured("Inference must use HTTPS or a private service hostname")
    if not IMPORT_INFERENCE_TOKEN:
        raise ImproperlyConfigured("IMPORT_INFERENCE_TOKEN is required when OCR is enabled")
if EMAIL_BACKEND in {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}:
    raise ImproperlyConfigured("A production email backend is required")
if DEFAULT_FROM_EMAIL == "TestFlow <noreply@localhost>":
    raise ImproperlyConfigured("DEFAULT_FROM_EMAIL must be configured for production")
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and not EMAIL_HOST:
    raise ImproperlyConfigured("EMAIL_HOST is required for the SMTP backend")

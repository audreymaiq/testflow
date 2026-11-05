"""Production settings for an HTTPS reverse proxy with a private app port."""

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

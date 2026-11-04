"""Production settings. TLS headers and HSTS are finalized during S6."""

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
REFRESH_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
if not ALLOWED_HOSTS or not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("Production host and origin allowlists are required")

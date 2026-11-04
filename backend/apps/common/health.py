"""Minimal public readiness probe without sensitive infrastructure details."""

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from redis import Redis


@require_GET
def healthz(_request):
    database_ok = False
    redis_ok = False
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            database_ok = cursor.fetchone() == (1,)
    except Exception:
        pass
    try:
        if settings.REDIS_URL:
            with Redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
            ) as redis:
                redis_ok = bool(redis.ping())
    except Exception:
        pass
    healthy = database_ok and redis_ok
    return JsonResponse(
        {"status": "ok" if healthy else "unavailable", "database": database_ok, "redis": redis_ok},
        status=200 if healthy else 503,
    )

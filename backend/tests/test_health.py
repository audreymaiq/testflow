import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_reports_real_database_and_redis(settings):
    response = Client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True, "redis": True}
    settings.REDIS_URL = "redis://127.0.0.1:1/0"
    unavailable = Client().get("/healthz")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"status": "unavailable", "database": True, "redis": False}


@pytest.mark.django_db
def test_request_id_is_safe_and_echoed():
    client = Client()
    supplied = client.get("/healthz", HTTP_X_REQUEST_ID="test-request-123")
    assert supplied["X-Request-ID"] == "test-request-123"
    invalid = client.get("/healthz", HTTP_X_REQUEST_ID="bad\nheader")
    assert invalid["X-Request-ID"] != "bad\nheader"
    assert len(invalid["X-Request-ID"]) == 32

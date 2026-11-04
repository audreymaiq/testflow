"""Request correlation and small JSON stdout logs without request bodies."""

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from time import monotonic

request_id_context: ContextVar[str] = ContextVar("request_id", default="")
REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
logger = logging.getLogger("testflow.request")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        request = getattr(record, "request", None)
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                getattr(request, "request_id", request_id_context.get()),
            ),
        }
        for key in (
            "method",
            "path",
            "status",
            "duration_ms",
            "import_job_id",
            "stage",
            "latency_ms",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_context.set(request_id)
        started = monotonic()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((monotonic() - started) * 1000, 2),
                },
            )
            return response
        except Exception:
            logger.exception(
                "request failed",
                extra={"method": request.method, "path": request.path},
            )
            raise
        finally:
            request_id_context.reset(token)

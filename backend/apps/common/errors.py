"""Small domain error hierarchy and stable API error shape."""

from rest_framework.response import Response
from rest_framework.views import exception_handler


class AppError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationFailed(AppError):
    status_code = 400


class NotFound(AppError):
    status_code = 404


class DomainPermissionDenied(AppError):
    status_code = 403


class Conflict(AppError):
    status_code = 409


class QuotaExceeded(AppError):
    status_code = 429


class ExternalServiceError(AppError):
    status_code = 502

    def __init__(self, code: str, message: str, details=None, retryable: bool = False):
        self.retryable = retryable
        super().__init__(code, message, details)


def api_exception_handler(exc, context):
    if isinstance(exc, AppError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status=exc.status_code,
        )
    response = exception_handler(exc, context)
    if response is not None:
        details = response.data
        if isinstance(details, dict):
            first = next(iter(details.values()), "Yêu cầu không hợp lệ.")
            message = str(first[0] if isinstance(first, list) and first else first)
        else:
            message = str(details)
        response.data = {
            "error": {
                "code": str(getattr(exc, "default_code", "error")),
                "message": message,
                "details": details,
            }
        }
    return response

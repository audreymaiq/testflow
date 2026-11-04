from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.catalog.services import is_admin
from apps.common.errors import DomainPermissionDenied

from .selectors import summary


class OperationsSummaryView(GenericAPIView):
    @extend_schema(operation_id="operations_summary", responses={200: dict})
    def get(self, request):
        if not is_admin(request.user):
            raise DomainPermissionDenied("ADMIN_REQUIRED", "Chỉ quản trị viên được xem vận hành.")
        return Response(summary())

"""Authenticated, owner-scoped import and review API."""

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.catalog.services import is_reviewer
from apps.common.errors import DomainPermissionDenied, NotFound

from .models import ImportJob, PageResult
from .serializers import (
    DiscardSerializer,
    DraftReplaceSerializer,
    ImageUploadSerializer,
    TxtUploadSerializer,
)
from .services import (
    confirm,
    create_image_job,
    create_txt_job,
    discard,
    job_payload,
    replace_draft,
    reviewable_job,
)


class TxtImportView(GenericAPIView):
    serializer_class = TxtUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = create_txt_job(
            serializer.validated_data["file"],
            uploader=request.user,
            duration_mode=serializer.validated_data["duration_mode"],
            duration_minutes=serializer.validated_data.get("duration_minutes"),
        )
        return Response(job_payload(job), status=status.HTTP_201_CREATED)


class ImageImportView(GenericAPIView):
    serializer_class = ImageUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = create_image_job(
            serializer.validated_data["file"],
            uploader=request.user,
            subject_hint=serializer.validated_data.get("subject_hint", ""),
        )
        return Response(job_payload(job), status=status.HTTP_202_ACCEPTED)


class MineView(GenericAPIView):
    @extend_schema(operation_id="imports_mine", responses={200: dict})
    def get(self, request):
        queryset = (
            ImportJob.objects.filter(uploader=request.user)
            .select_related("draft")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([job_payload(job) for job in page])


class ReviewQueueView(GenericAPIView):
    @extend_schema(operation_id="imports_review_queue", responses={200: dict})
    def get(self, request):
        if not is_reviewer(request.user):
            raise DomainPermissionDenied("REVIEWER_REQUIRED", "Cần quyền duyệt đề.")
        queryset = (
            ImportJob.objects.filter(status=ImportJob.Status.NEEDS_REVIEW)
            .select_related("draft")
            .order_by("-draft__priority_score", "created_at")
        )
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([job_payload(job) for job in page])


class ReviewView(GenericAPIView):
    serializer_class = DraftReplaceSerializer

    def get(self, request, job_id):
        job = reviewable_job(job_id, user=request.user)
        return Response(job_payload(job, include_draft=True))

    def patch(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = replace_draft(job_id, user=request.user, data=serializer.validated_data["draft"])
        return Response(job_payload(job, include_draft=True))


class OriginalFileView(GenericAPIView):
    @extend_schema(operation_id="imports_original_file", responses={200: bytes})
    def get(self, request, job_id):
        job = reviewable_job(job_id, user=request.user)
        try:
            source = job.original_file.open("rb")
        except (FileNotFoundError, OSError) as exc:
            raise NotFound("IMPORT_FILE_NOT_FOUND", "Không tìm thấy tệp gốc.") from exc
        response = FileResponse(
            source,
            as_attachment=True,
            filename=job.original_filename,
            content_type=job.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class PageImageView(GenericAPIView):
    @extend_schema(operation_id="imports_page_image", responses={200: bytes})
    def get(self, request, job_id, page_no):
        job = reviewable_job(job_id, user=request.user)
        page = PageResult.objects.filter(job=job, page_no=page_no).first()
        if page is None or not page.image:
            raise NotFound("IMPORT_PAGE_NOT_FOUND", "Không tìm thấy ảnh trang.")
        try:
            image = page.image.open("rb")
        except (FileNotFoundError, OSError) as exc:
            raise NotFound("IMPORT_PAGE_NOT_FOUND", "Không tìm thấy ảnh trang.") from exc
        response = FileResponse(image, content_type="image/png")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ConfirmView(GenericAPIView):
    @extend_schema(operation_id="imports_confirm", request=None, responses={200: dict})
    def post(self, request, job_id):
        exam = confirm(job_id, user=request.user)
        return Response({"exam_id": str(exam.id)})


class DiscardView(GenericAPIView):
    serializer_class = DiscardSerializer

    @extend_schema(operation_id="imports_discard", responses={200: dict})
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = discard(job_id, user=request.user, reason=serializer.validated_data.get("reason", ""))
        return Response(job_payload(job))

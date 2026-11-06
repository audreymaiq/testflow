"""Authenticated, owner-scoped TXT import API."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import ImportJob
from .serializers import DiscardSerializer, DraftReplaceSerializer, TxtUploadSerializer
from .services import confirm, create_txt_job, discard, job_payload, replace_draft


class TxtImportView(GenericAPIView):
    serializer_class = TxtUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = create_txt_job(serializer.validated_data["file"], uploader=request.user)
        return Response(job_payload(job), status=status.HTTP_201_CREATED)


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


class ReviewView(GenericAPIView):
    serializer_class = DraftReplaceSerializer

    def get(self, request, job_id):
        job = get_object_or_404(
            ImportJob.objects.select_related("draft"), pk=job_id, uploader=request.user
        )
        return Response(job_payload(job, include_draft=True))

    def patch(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = replace_draft(job_id, user=request.user, data=serializer.validated_data["draft"])
        return Response(job_payload(job, include_draft=True))


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

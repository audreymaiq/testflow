"""Read-only public catalog and authenticated manual creation."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.errors import DomainPermissionDenied

from .models import PublishRequest, Subject, Visibility
from .selectors import list_exams, publication_queue, visible_exams
from .serializers import (
    ExamDetailSerializer,
    ExamFilterSerializer,
    ExamListSerializer,
    FacetsResponseSerializer,
    ManualCreateSerializer,
    PreviewResponseSerializer,
    PublicationDecisionSerializer,
    PublicationDetailSerializer,
    PublicationFilterSerializer,
    PublicationRequestSerializer,
    SubjectSerializer,
    VisibilityChangeSerializer,
    VisibilityResponseSerializer,
)
from .services import (
    create_exam,
    decide_publication,
    hide_exam,
    is_reviewer,
    make_private,
    request_publication,
    soft_delete_exam,
)


class ExamListView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ExamListSerializer

    @extend_schema(operation_id="exams_list", parameters=[ExamFilterSerializer])
    def get(self, request):
        filters = ExamFilterSerializer(data=request.query_params.dict())
        filters.is_valid(raise_exception=True)
        queryset = list_exams(request.user, filters.validated_data)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class ManualExamView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ManualCreateSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam = create_exam(serializer.validated_data["draft"], owner=request.user)
        return Response(ExamDetailSerializer(exam).data, status=status.HTTP_201_CREATED)


class ExamDetailView(GenericAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    serializer_class = ExamDetailSerializer

    @extend_schema(operation_id="exams_retrieve")
    def get(self, request, exam_id):
        exam = get_object_or_404(
            visible_exams(request.user)
            .select_related("subject")
            .prefetch_related("schools", "majors", "chapters", "sections"),
            pk=exam_id,
        )
        return Response(self.get_serializer(exam).data)

    def delete(self, request, exam_id):
        soft_delete_exam(exam_id, owner=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExamPreviewView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PreviewResponseSerializer

    def get(self, request, exam_id):
        exam = get_object_or_404(visible_exams(request.user), pk=exam_id)
        sections = exam.sections.order_by("order").prefetch_related("questions__choices")
        preview = []
        for section in sections:
            for question in section.questions.all():
                preview.append(
                    {
                        "id": str(question.id),
                        "kind": question.kind,
                        "text": question.text,
                        "choices": [
                            {"label": choice.label, "text": choice.text}
                            for choice in question.choices.all()
                        ],
                    }
                )
                if len(preview) == 3:
                    return Response({"questions": preview})
        return Response({"questions": preview})


class FacetsView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = FacetsResponseSerializer

    def get(self, request):
        exams = visible_exams(request.user)
        return Response(
            {
                "subjects": list(
                    exams.values_list("subject__code", "subject__name")
                    .distinct()
                    .order_by("subject__name")
                ),
                "schools": list(
                    exams.exclude(schools__isnull=True)
                    .values_list("schools__name", flat=True)
                    .distinct()
                    .order_by("schools__name")
                ),
                "majors": list(
                    exams.exclude(majors__isnull=True)
                    .values_list("majors__name", flat=True)
                    .distinct()
                    .order_by("majors__name")
                ),
                "levels": list(exams.values_list("level", flat=True).distinct().order_by("level")),
            }
        )


class SubjectListView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SubjectSerializer

    def get(self, request):
        subjects = Subject.objects.filter(is_active=True).order_by("name")
        return Response(self.get_serializer(subjects, many=True).data)


class VisibilityView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = VisibilityChangeSerializer

    @extend_schema(responses={200: VisibilityResponseSerializer})
    def post(self, request, exam_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["visibility"] == Visibility.PRIVATE:
            exam = make_private(exam_id, owner=request.user)
            return Response({"visibility": exam.visibility, "request_id": None})
        publication = request_publication(exam_id, owner=request.user)
        return Response({"visibility": Visibility.PRIVATE, "request_id": publication.pk})


class PublicationQueueView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PublicationRequestSerializer

    @extend_schema(operation_id="publish_requests_list", parameters=[PublicationFilterSerializer])
    def get(self, request):
        if not is_reviewer(request.user):
            raise DomainPermissionDenied("REVIEWER_REQUIRED", "Cần quyền duyệt đề.")
        filters = PublicationFilterSerializer(data=request.query_params.dict())
        filters.is_valid(raise_exception=True)
        page = self.paginate_queryset(publication_queue(filters.validated_data["status"]))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class PublicationDetailView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PublicationDetailSerializer

    @extend_schema(operation_id="publish_requests_retrieve")
    def get(self, request, request_id):
        if not is_reviewer(request.user):
            raise DomainPermissionDenied("REVIEWER_REQUIRED", "Cần quyền duyệt đề.")
        publication = get_object_or_404(
            PublishRequest.objects.select_related("exam", "requested_by").filter(
                exam__deleted_at__isnull=True,
                exam__visibility=Visibility.PRIVATE,
                status="PENDING",
            ),
            pk=request_id,
        )
        return Response(self.get_serializer(publication).data)


class PublicationDecisionView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PublicationDecisionSerializer

    @extend_schema(responses={200: PublicationRequestSerializer})
    def post(self, request, request_id, decision):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        publication = decide_publication(
            request_id,
            reviewer=request.user,
            approve=decision == "approve",
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(PublicationRequestSerializer(publication).data)


class AdminHideView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = VisibilityChangeSerializer

    @extend_schema(request=None, responses={200: ExamDetailSerializer})
    def post(self, request, exam_id):
        exam = hide_exam(exam_id, admin=request.user)
        return Response(ExamDetailSerializer(exam).data)

"""Read-only public catalog and authenticated manual creation."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Subject
from .selectors import list_exams, visible_exams
from .serializers import (
    ExamDetailSerializer,
    ExamFilterSerializer,
    ExamListSerializer,
    FacetsResponseSerializer,
    ManualCreateSerializer,
    PreviewResponseSerializer,
    SubjectSerializer,
)
from .services import create_exam


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
    permission_classes = (AllowAny,)
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

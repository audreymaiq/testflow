from django.urls import path

from .views import (
    ExamDetailView,
    ExamListView,
    ExamPreviewView,
    FacetsView,
    ManualExamView,
    SubjectListView,
)

urlpatterns = [
    path("exams/", ExamListView.as_view(), name="exam-list"),
    path("exams/manual/", ManualExamView.as_view(), name="exam-manual"),
    path("exams/<uuid:exam_id>/", ExamDetailView.as_view(), name="exam-detail"),
    path("exams/<uuid:exam_id>/preview/", ExamPreviewView.as_view(), name="exam-preview"),
    path("facets/", FacetsView.as_view(), name="facets"),
    path("subjects/", SubjectListView.as_view(), name="subjects"),
]

from django.urls import path

from .views import (
    AdminHideView,
    ExamAssetView,
    ExamDetailView,
    ExamListView,
    ExamPreviewView,
    FacetsView,
    ManualExamView,
    ProfileSchoolView,
    PublicationDecisionView,
    PublicationDetailView,
    PublicationQueueView,
    SubjectListView,
    TaxonomyCreateView,
    TaxonomyLookupView,
    VisibilityView,
)

urlpatterns = [
    path("exams/", ExamListView.as_view(), name="exam-list"),
    path("exams/manual/", ManualExamView.as_view(), name="exam-manual"),
    path("exams/<uuid:exam_id>/", ExamDetailView.as_view(), name="exam-detail"),
    path(
        "exams/<uuid:exam_id>/assets/<uuid:asset_id>/",
        ExamAssetView.as_view(),
        name="exam-asset",
    ),
    path("exams/<uuid:exam_id>/preview/", ExamPreviewView.as_view(), name="exam-preview"),
    path("exams/<uuid:exam_id>/visibility/", VisibilityView.as_view(), name="exam-visibility"),
    path("exams/<uuid:exam_id>/hide/", AdminHideView.as_view(), name="exam-hide"),
    path("publish-requests/", PublicationQueueView.as_view(), name="publish-request-list"),
    path(
        "publish-requests/<int:request_id>/",
        PublicationDetailView.as_view(),
        name="publish-request-detail",
    ),
    path(
        "publish-requests/<int:request_id>/approve/",
        PublicationDecisionView.as_view(),
        {"decision": "approve"},
        name="publish-request-approve",
    ),
    path(
        "publish-requests/<int:request_id>/reject/",
        PublicationDecisionView.as_view(),
        {"decision": "reject"},
        name="publish-request-reject",
    ),
    path("facets/", FacetsView.as_view(), name="facets"),
    path("subjects/", SubjectListView.as_view(), name="subjects"),
    path("taxonomy/lookup/", TaxonomyLookupView.as_view(), name="taxonomy-lookup"),
    path("taxonomy/names/", TaxonomyCreateView.as_view(), name="taxonomy-create"),
    path("taxonomy/profile-school/", ProfileSchoolView.as_view(), name="taxonomy-profile-school"),
]

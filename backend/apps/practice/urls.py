from django.urls import path

from .views import (
    AnswerView,
    ExamPracticeSummaryView,
    HistoryView,
    ResultView,
    SessionDetailView,
    SessionListCreateView,
    SkipView,
    StatsView,
    SubmitView,
)

urlpatterns = [
    path("sessions/", SessionListCreateView.as_view(), name="practice-sessions"),
    path("sessions/history/", HistoryView.as_view(), name="practice-history"),
    path("stats/", StatsView.as_view(), name="practice-stats"),
    path(
        "exams/<uuid:exam_id>/summary/",
        ExamPracticeSummaryView.as_view(),
        name="practice-exam-summary",
    ),
    path("sessions/<uuid:session_id>/", SessionDetailView.as_view(), name="practice-session"),
    path(
        "sessions/<uuid:session_id>/answers/<uuid:question_id>/",
        AnswerView.as_view(),
        name="practice-answer",
    ),
    path(
        "sessions/<uuid:session_id>/skip/<uuid:question_id>/",
        SkipView.as_view(),
        name="practice-skip",
    ),
    path("sessions/<uuid:session_id>/submit/", SubmitView.as_view(), name="practice-submit"),
    path("sessions/<uuid:session_id>/result/", ResultView.as_view(), name="practice-result"),
]

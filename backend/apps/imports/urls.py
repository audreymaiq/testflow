from django.urls import path

from .views import (
    ConfirmView,
    DiscardView,
    ImageImportView,
    MineView,
    OriginalFileView,
    ReviewQueueView,
    ReviewView,
    TxtImportView,
)

urlpatterns = [
    path("txt/", TxtImportView.as_view(), name="imports-txt"),
    path("image/", ImageImportView.as_view(), name="imports-image"),
    path("mine/", MineView.as_view(), name="imports-mine"),
    path("review-queue/", ReviewQueueView.as_view(), name="imports-review-queue"),
    path("<uuid:job_id>/", ReviewView.as_view(), name="imports-detail"),
    path("<uuid:job_id>/original/", OriginalFileView.as_view(), name="imports-original"),
    path("<uuid:job_id>/confirm/", ConfirmView.as_view(), name="imports-confirm"),
    path("<uuid:job_id>/discard/", DiscardView.as_view(), name="imports-discard"),
]

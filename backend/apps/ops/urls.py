from django.urls import path

from .views import OperationsSummaryView

urlpatterns = [path("summary/", OperationsSummaryView.as_view(), name="ops-summary")]

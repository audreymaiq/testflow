"""Small query-bound operational snapshot without student content."""

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from apps.catalog.models import PublishRequest, PublishRequestStatus
from apps.imports.models import ImportJob


def summary():
    counts = {status: 0 for status, _label in ImportJob.Status.choices}
    counts.update(
        {
            row["status"]: row["count"]
            for row in ImportJob.objects.values("status").annotate(count=Count("id"))
        }
    )
    oldest = (
        ImportJob.objects.filter(status=ImportJob.Status.NEEDS_REVIEW)
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    publication_pending = PublishRequest.objects.filter(status=PublishRequestStatus.PENDING).count()
    return {
        "build_sha": settings.BUILD_SHA,
        "import_jobs_by_status": counts,
        "oldest_import_review_age_seconds": (
            round((timezone.now() - oldest).total_seconds()) if oldest else None
        ),
        "pending_publication_requests": publication_pending,
    }

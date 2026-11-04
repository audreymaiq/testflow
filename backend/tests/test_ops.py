import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_admin_operations_summary_is_private_and_counts_jobs(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.BUILD_SHA = "test-build-123"
    owner = get_user_model().objects.create_user(
        "ops_owner", email="ops_owner@example.com", password="HardToGuess#2026"
    )
    admin = get_user_model().objects.create_user(
        "ops_admin", email="ops_admin@example.com", password="HardToGuess#2026", is_staff=True
    )
    admin.groups.add(Group.objects.get(name="Admin"))
    owner_client = APIClient()
    owner_client.force_authenticate(owner)
    upload = SimpleUploadedFile(
        "ops.txt", b"#TITLE: Ops\n[C1] Math\nQuestion?\nA. One\nB. Two\n=>B\n"
    )
    created = owner_client.post("/api/v1/imports/txt/", {"file": upload}, format="multipart")
    assert created.status_code == 201
    assert APIClient().get("/api/v1/ops/summary/").status_code == 401
    assert owner_client.get("/api/v1/ops/summary/").status_code == 403
    admin_client = APIClient()
    admin_client.force_authenticate(admin)
    result = admin_client.get("/api/v1/ops/summary/")
    assert result.status_code == 200
    assert result.data["build_sha"] == "test-build-123"
    assert result.data["import_jobs_by_status"]["NEEDS_REVIEW"] == 1
    assert result.data["pending_publication_requests"] == 0
    assert result.data["oldest_import_review_age_seconds"] >= 0
    assert "Ops" not in str(result.data)

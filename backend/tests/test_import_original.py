"""Private original-file access for import review."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.imports.models import ImportJob


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


@pytest.mark.django_db(transaction=True)
def test_original_file_is_only_streamed_to_owner_or_reviewer(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    User = get_user_model()
    owner = User.objects.create_user(
        "source_owner", email="source_owner@example.com", password="HardToGuess#2026"
    )
    other = User.objects.create_user(
        "source_other", email="source_other@example.com", password="HardToGuess#2026"
    )
    reviewer = User.objects.create_user(
        "source_reviewer", email="source_reviewer@example.com", password="HardToGuess#2026"
    )
    reviewer.groups.add(Group.objects.get_or_create(name="Reviewer")[0])
    raw = b"#TITLE: Synthetic exam\n[CH1] Section\nQuestion?\nA. Yes\nB. No\n=>A\n"
    uploaded = client(owner).post(
        "/api/v1/imports/txt/",
        {"file": SimpleUploadedFile("source.txt", raw)},
        format="multipart",
    )
    assert uploaded.status_code == 201
    job = ImportJob.objects.get(pk=uploaded.data["id"])
    assert job.original_file.storage.exists(job.original_file.name)
    url = f"/api/v1/imports/{job.id}/original/"

    assert client().get(url).status_code == 401
    assert client(other).get(url).status_code == 404
    for actor in (owner, reviewer):
        response = client(actor).get(url)
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == raw
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert "attachment" in response["Content-Disposition"]
        response.close()

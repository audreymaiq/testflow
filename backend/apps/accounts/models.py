"""Identity and minimal optional profile fields."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from apps.common.text import normalize_text


class User(AbstractUser):
    username: str
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=160, blank=True)
    school = models.CharField(max_length=160, blank=True)
    grade = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(Lower("username"), name="accounts_username_ci_unique"),
            models.UniqueConstraint(Lower("email"), name="accounts_email_ci_unique"),
        )

    def save(self, *args, **kwargs):
        self.username = normalize_text(self.username)
        self.email = normalize_text(self.email).lower()
        self.display_name = normalize_text(self.display_name)
        self.school = normalize_text(self.school)
        self.grade = normalize_text(self.grade)
        super().save(*args, **kwargs)

"""Canonical taxonomy lookup and explicit self-service additions."""

import hashlib
import re
from difflib import SequenceMatcher

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.errors import Conflict, ValidationFailed
from apps.common.text import normalize_text, search_fold

from .models import Major, School, Subject, TaxonomyAlias, TaxonomyKind, TaxonomyProposal

MODELS = {TaxonomyKind.SUBJECT: Subject, TaxonomyKind.SCHOOL: School, TaxonomyKind.MAJOR: Major}
FIELDS = {
    TaxonomyKind.SUBJECT: "subject",
    TaxonomyKind.SCHOOL: "school",
    TaxonomyKind.MAJOR: "major",
}


def name_key(value: str) -> str:
    return " ".join(normalize_text(value).casefold().split())


def clean_name(value: str) -> str:
    name = " ".join(normalize_text(value).split())
    if (
        not name
        or len(name) > 200
        or len(name_key(name)) > 200
        or not any(char.isalnum() for char in name)
    ):
        raise ValidationFailed(
            "TAXONOMY_NAME_INVALID", "Tên phải có chữ hoặc số và dài tối đa 200 ký tự."
        )
    return name


def _model(kind: str):
    if kind not in MODELS:
        raise ValidationFailed("TAXONOMY_KIND_INVALID", "Loại danh mục không hợp lệ.")
    return MODELS[kind]


def resolve(kind: str, value: str):
    model = _model(kind)
    key = name_key(value)
    if not key:
        return None
    if kind == TaxonomyKind.SUBJECT:
        by_code = model.objects.filter(code=value, is_active=True).first()
        if by_code:
            return by_code
    alias = TaxonomyAlias.objects.filter(kind=kind, key=key).select_related(FIELDS[kind]).first()
    if alias:
        target = getattr(alias, FIELDS[kind])
        return target if kind != TaxonomyKind.SUBJECT or target.is_active else None
    matches = [item for item in model.objects.all() if name_key(item.name) == key]
    if kind == TaxonomyKind.SUBJECT:
        matches = [item for item in matches if item.is_active]
    # Legacy rows may already contain ambiguous variants. Never guess between them.
    return matches[0] if len(matches) == 1 else None


def suggestions(kind: str, value: str) -> list[dict]:
    model = _model(kind)
    key = search_fold(" ".join(value.split()))
    if not key:
        return []
    ranked = sorted(
        (
            (SequenceMatcher(None, key, search_fold(" ".join(item.name.split()))).ratio(), item)
            for item in model.objects.all()
        ),
        key=lambda pair: (-pair[0], pair[1].name),
    )
    return [
        {"id": item.pk, "name": item.name, "code": getattr(item, "code", None)}
        for score, item in ranked
        if score >= 0.55
    ][:5]


def lookup(kind: str, value: str) -> dict:
    clean = clean_name(value)
    target = resolve(kind, clean)
    return {
        "match": {"id": target.pk, "name": target.name, "code": getattr(target, "code", None)}
        if target
        else None,
        "suggestions": [] if target else suggestions(kind, clean),
    }


def register(kind: str, value: str, user, *, has_formula: bool = False):
    """Create a distinct canonical item only after the user explicitly chooses new."""
    if not user or not user.is_authenticated:
        raise ValidationFailed("OWNER_REQUIRED", "Cần đăng nhập để tạo tên mới.")
    model = _model(kind)
    name = clean_name(value)
    if kind == TaxonomyKind.SUBJECT and len(name) > 120:
        raise ValidationFailed("SUBJECT_NAME_TOO_LONG", "Tên môn dài tối đa 120 ký tự.")
    match = resolve(kind, name)
    if match:
        return match, False
    key = name_key(name)
    if any(name_key(item.name) == key for item in model.objects.all()):
        raise Conflict("TAXONOMY_AMBIGUOUS", "Có nhiều tên cũ trùng nhau; chưa thể tạo tên mới.")
    try:
        with transaction.atomic():
            if kind == TaxonomyKind.SUBJECT:
                base = re.sub(r"[^a-z0-9]+", "-", search_fold(name)).strip("-")[:36]
                if not base:
                    base = "mon"
                digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
                code = f"{base}-{digest[:12]}"
                if Subject.objects.filter(code=code).exists():
                    raise Conflict(
                        "SUBJECT_CODE_CONFLICT", "Mã môn bị trùng; cần kiểm tra dữ liệu."
                    )
                target = Subject.objects.create(
                    code=code, name=name, levels=[], has_formula=has_formula
                )
            else:
                target = model.objects.create(name=name)
            TaxonomyAlias.objects.create(kind=kind, key=key, **{FIELDS[kind]: target})
            TaxonomyProposal.objects.create(
                kind=kind,
                key=key,
                name=name,
                status=TaxonomyProposal.Status.APPROVED,
                requested_by=user,
                target_id=target.pk,
                reason="SELF_SERVICE",
                decided_at=timezone.now(),
            )
            return target, True
    except IntegrityError as exc:
        match = resolve(kind, name)
        if match:
            return match, False
        raise Conflict("TAXONOMY_CONFLICT", "Danh mục vừa thay đổi; vui lòng thử lại.") from exc

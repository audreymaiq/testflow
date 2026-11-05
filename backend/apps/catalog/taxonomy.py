"""Canonical taxonomy lookup and human-reviewed additions."""

import re
from difflib import SequenceMatcher

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.errors import Conflict, DomainPermissionDenied, NotFound, ValidationFailed
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


def propose(kind: str, value: str, user):
    _model(kind)
    name = clean_name(value)
    match = resolve(kind, name)
    if match:
        return None, match
    key = name_key(name)
    try:
        with transaction.atomic():
            proposal, _ = TaxonomyProposal.objects.get_or_create(
                kind=kind,
                key=key,
                status=TaxonomyProposal.Status.PENDING,
                defaults={"name": name, "requested_by": user},
            )
            return proposal, None
    except IntegrityError as exc:
        raise Conflict("TAXONOMY_CONFLICT", "Tên này đang được xử lý; vui lòng tải lại.") from exc


@transaction.atomic
def decide(
    proposal_id: int,
    *,
    admin,
    action: str,
    target_id: int | None = None,
    canonical_name: str = "",
    code: str = "",
    levels: list[str] | None = None,
    has_formula: bool = False,
    reason: str = "",
):
    from .services import is_admin

    if not is_admin(admin):
        raise DomainPermissionDenied("ADMIN_REQUIRED", "Cần quyền Admin để duyệt danh mục.")
    proposal = TaxonomyProposal.objects.select_for_update().filter(pk=proposal_id).first()
    if proposal is None:
        raise NotFound("PROPOSAL_NOT_FOUND", "Không tìm thấy đề xuất.")
    if proposal.status != TaxonomyProposal.Status.PENDING:
        raise Conflict("PROPOSAL_DECIDED", "Đề xuất đã được xử lý.")
    if action not in {"MAP", "CREATE", "REJECT"}:
        raise ValidationFailed("ACTION_INVALID", "Quyết định không hợp lệ.")
    target = None
    if action == "MAP":
        target = _model(proposal.kind).objects.filter(pk=target_id).first()
        if target is None or (proposal.kind == TaxonomyKind.SUBJECT and not target.is_active):
            raise ValidationFailed(
                "TARGET_INVALID", "Bản ghi chuẩn không tồn tại hoặc đã ngừng dùng."
            )
    elif action == "CREATE":
        name = clean_name(canonical_name or proposal.name)
        if any(
            name_key(item.name) == name_key(name) for item in _model(proposal.kind).objects.all()
        ):
            raise Conflict("CANONICAL_EXISTS", "Tên chuẩn đã tồn tại. Hãy chọn liên kết.")
        if resolve(proposal.kind, name):
            raise Conflict("CANONICAL_EXISTS", "Tên chuẩn đã tồn tại. Hãy chọn liên kết.")
        if proposal.kind == TaxonomyKind.SUBJECT:
            subject_code = code or re.sub(r"[^a-z0-9]+", "-", search_fold(name)).strip("-")
            if (
                not subject_code
                or len(subject_code) > 50
                or Subject.objects.filter(code=subject_code).exists()
            ):
                raise ValidationFailed(
                    "SUBJECT_CODE_INVALID", "Mã môn không hợp lệ hoặc đã tồn tại."
                )
            target = Subject.objects.create(
                code=subject_code, name=name, levels=levels or [], has_formula=has_formula
            )
        else:
            target = _model(proposal.kind).objects.create(name=name)
        TaxonomyAlias.objects.create(
            kind=proposal.kind, key=name_key(name), **{FIELDS[proposal.kind]: target}
        )
    elif not reason.strip():
        raise ValidationFailed("REASON_REQUIRED", "Cần lý do khi từ chối.")
    if target is not None:
        existing = TaxonomyAlias.objects.filter(kind=proposal.kind, key=proposal.key).first()
        if existing and getattr(existing, f"{FIELDS[proposal.kind]}_id") != target.pk:
            raise Conflict("ALIAS_CONFLICT", "Tên này đã liên kết với bản ghi khác.")
        if not existing:
            TaxonomyAlias.objects.create(
                kind=proposal.kind, key=proposal.key, **{FIELDS[proposal.kind]: target}
            )
    proposal.status = (
        TaxonomyProposal.Status.REJECTED if action == "REJECT" else TaxonomyProposal.Status.APPROVED
    )
    proposal.reviewed_by = admin
    proposal.target_id = target.pk if target else None
    proposal.reason = reason.strip()
    proposal.decided_at = timezone.now()
    proposal.save()
    return proposal

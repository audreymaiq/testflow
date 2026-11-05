"""Carry old pending proposals into the self-service taxonomy without deleting audit rows."""

import hashlib
import re
import unicodedata

from django.db import migrations
from django.utils import timezone


def folded(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def slug(value):
    text = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    ascii_text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:36] or "mon"


def migrate_pending(apps, schema_editor):
    db = schema_editor.connection.alias
    Subject = apps.get_model("catalog", "Subject")
    School = apps.get_model("catalog", "School")
    Major = apps.get_model("catalog", "Major")
    Alias = apps.get_model("catalog", "TaxonomyAlias")
    Proposal = apps.get_model("catalog", "TaxonomyProposal")
    models = {"SUBJECT": Subject, "SCHOOL": School, "MAJOR": Major}
    fields = {"SUBJECT": "subject", "SCHOOL": "school", "MAJOR": "major"}
    for proposal in Proposal.objects.using(db).filter(status="PENDING").order_by("id"):
        model = models[proposal.kind]
        name = " ".join(unicodedata.normalize("NFC", proposal.name).split())
        key = folded(name)
        alias = Alias.objects.using(db).filter(kind=proposal.kind, key=key).first()
        target = getattr(alias, fields[proposal.kind]) if alias else None
        if proposal.kind == "SUBJECT" and target is not None and not target.is_active:
            proposal.status = "REJECTED"
            proposal.reason = "SELF_SERVICE_REENTER_REQUIRED"
            proposal.decided_at = timezone.now()
            proposal.save(using=db, update_fields=("status", "reason", "decided_at", "updated_at"))
            continue
        if target is None:
            matches = [item for item in model.objects.using(db).all() if folded(item.name) == key]
            if proposal.kind == "SUBJECT":
                matches = [item for item in matches if item.is_active]
            if len(matches) > 1 or (proposal.kind == "SUBJECT" and len(name) > 120):
                proposal.status = "REJECTED"
                proposal.reason = "SELF_SERVICE_REENTER_REQUIRED"
                proposal.decided_at = timezone.now()
                proposal.save(
                    using=db, update_fields=("status", "reason", "decided_at", "updated_at")
                )
                continue
            target = matches[0] if matches else None
        if target is None:
            if proposal.kind == "SUBJECT":
                digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
                code = f"{slug(name)}-{digest[:12]}"
                if Subject.objects.using(db).filter(code=code).exists():
                    proposal.status = "REJECTED"
                    proposal.reason = "SELF_SERVICE_REENTER_REQUIRED"
                    proposal.decided_at = timezone.now()
                    proposal.save(
                        using=db, update_fields=("status", "reason", "decided_at", "updated_at")
                    )
                    continue
                target = Subject.objects.using(db).create(
                    code=code, name=name, levels=[], has_formula=False
                )
            else:
                target = model.objects.using(db).create(name=name)
        if alias is None:
            Alias.objects.using(db).create(
                kind=proposal.kind, key=key, **{fields[proposal.kind]: target}
            )
        proposal.status = "APPROVED"
        proposal.target_id = target.pk
        proposal.reason = "SELF_SERVICE_MIGRATED"
        proposal.decided_at = timezone.now()
        proposal.save(
            using=db, update_fields=("status", "target_id", "reason", "decided_at", "updated_at")
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_alter_taxonomyproposal_target_id_and_more")]
    operations = [migrations.RunPython(migrate_pending, migrations.RunPython.noop)]

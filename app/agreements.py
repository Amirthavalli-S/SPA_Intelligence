"""Which agreement a document belongs to, what kind of document it is, and when it was signed.

A real SPA is changed over time by addenda and extension letters. Each of those PDFs only says what CHANGED, so to know the
current terms we must group the documents of one agreement (see reconcile.py). This module only stores and validates that
grouping. One small JSON file per document, saved next to the other app data and mirrored to the database like the rest.
Documents that ship with the app (samples) can carry defaults in samples/agreements.json; a saved choice overrides them.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from app import config

DOC_TYPES = ("SPA", "Addendum", "Extension Letter", "RERA Filing", "Brochure", "CRM Export")
AMENDING_TYPES = ("SPA", "Addendum", "Extension Letter")          # the documents that define or change ONE agreement
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
CID_RE = re.compile(r"^[0-9a-f]{64}$")


class AgreementError(ValueError):
    pass


def _path(contract_id: str) -> Path:
    if not CID_RE.match(contract_id):
        raise AgreementError("invalid contract id")
    return config.AGREEMENT_DIR / f"{contract_id}.json"


def sample_defaults() -> dict[str, dict]:
    p = config.SAMPLES_DIR / "agreements.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def get(contract_id: str, name: str = "") -> dict:
    """{agreement_id, doc_type, date_signed (ISO string)}, each None when not set. A saved choice wins over a sample default."""
    try:
        saved = json.loads(_path(contract_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, AgreementError):
        saved = None
    src = saved if isinstance(saved, dict) else sample_defaults().get(name, {})
    return {"agreement_id": src.get("agreement_id") or None, "doc_type": src.get("doc_type") or None,
            "date_signed": src.get("date_signed") or None}


def validate(agreement_id: Optional[str], doc_type: Optional[str], date_signed: Optional[date | str]) -> dict:
    aid = (agreement_id or "").strip() or None
    if aid is not None and not ID_RE.match(aid):
        raise AgreementError("agreement_id may use letters, digits, '.', '_' and '-' (max 40 characters)")
    if doc_type is not None and doc_type not in DOC_TYPES:
        raise AgreementError("doc_type must be one of: " + ", ".join(DOC_TYPES))
    ds = None
    if date_signed not in (None, ""):
        try:
            ds = date_signed if isinstance(date_signed, date) else date.fromisoformat(str(date_signed))
        except ValueError:
            raise AgreementError("date_signed must be a date like 2026-03-10") from None
        if ds.year < 1990 or ds > date.today().replace(year=date.today().year + 5):
            raise AgreementError("date_signed is outside a believable range")
    return {"agreement_id": aid, "doc_type": doc_type, "date_signed": ds.isoformat() if ds else None}


def set_meta(contract_id: str, agreement_id: Optional[str], doc_type: Optional[str], date_signed, by: str = "") -> dict:
    meta = validate(agreement_id, doc_type, date_signed)
    p = _path(contract_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = meta | {"updated_by": by[:80], "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    tmp.replace(p)
    return meta

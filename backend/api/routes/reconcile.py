"""Agreements: group a contract's documents (SPA, addenda, extension letters) and show the CURRENT effective terms."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import agreements, reconcile
from app.review import review_items
from backend.api import auth, deps
from backend.api.deps import ApiError

router = APIRouter(tags=["agreements"])
DocType = Literal["SPA", "Addendum", "Extension Letter", "RERA Filing", "Brochure", "CRM Export"]


class AgreementMeta(BaseModel):
    agreement_id: Optional[str] = None
    doc_type: Optional[DocType] = None
    date_signed: Optional[date] = None


def build(agreement_id: str) -> dict | None:
    """Recompute one agreement from the documents that carry its id. None when no document does."""
    docs, extra, open_total, currency = [], [], 0, None
    for s in deps.list_sources():
        m = agreements.get(s.id, s.name)
        if m["agreement_id"] != agreement_id:
            continue
        status, _ = deps.status_for(s)
        eff = deps.effective_contract(s) if status == "extracted" else None
        open_n = len(review_items(eff)) if eff else 0
        currency = currency or (eff.currency if eff else None)
        open_total += open_n
        if eff is None:
            extra.append(f"{s.name}: not extracted yet, so its terms are not merged.")
        ds = date.fromisoformat(m["date_signed"]) if m["date_signed"] else None
        docs.append((reconcile.Doc(s.id, s.name, m["doc_type"] or "SPA", ds, reconcile.fields_from_contract(eff) if eff else {}), open_n))
    if not docs:
        return None
    out = reconcile.reconcile(agreement_id, [d for d, _ in docs])
    for d, n in docs:
        next(x for x in out["documents"] if x["doc_id"] == d.doc_id)["open_reviews"] = n
    out["problems"] += extra
    out["currency"] = currency
    out["pending_review"] = open_total        # values a person still has to check: the current terms may change when they do
    return out


def effective_for_agreement(agreement_id: str):
    """(ContractData of the CURRENT terms, the attributes an amendment changed) for one agreement, or None if it cannot be built."""
    contracts, docs = {}, []
    for s in deps.list_sources():
        m = agreements.get(s.id, s.name)
        if m["agreement_id"] != agreement_id:
            continue
        status, _ = deps.status_for(s)
        eff = deps.effective_contract(s) if status == "extracted" else None
        ds = date.fromisoformat(m["date_signed"]) if m["date_signed"] else None
        docs.append(reconcile.Doc(s.id, s.name, m["doc_type"] or "SPA", ds, reconcile.fields_from_contract(eff) if eff else {}))
        if eff is not None:
            contracts[s.id] = eff
    usable = [d for d in docs if d.doc_id in contracts and d.doc_type == "SPA" and d.date_signed]
    if not usable:
        return None
    base = min(usable, key=lambda d: d.date_signed)
    result = reconcile.reconcile(agreement_id, [d for d in docs if d.doc_id in contracts])
    return reconcile.overlay_current(base.doc_id, result, contracts)


@router.get("/agreements")
def list_agreements():
    groups: dict[str, list[dict]] = {}
    for s in deps.list_sources():
        m = agreements.get(s.id, s.name)
        if m["agreement_id"]:
            groups.setdefault(m["agreement_id"], []).append(m | {"name": s.name})
    return [{"agreement_id": a, "documents": len(v), "latest_signed": max((x["date_signed"] for x in v if x["date_signed"]), default=None)}
            for a, v in sorted(groups.items())]


@router.get("/agreements/{agreement_id}")
def get_agreement(agreement_id: str):
    if not agreements.ID_RE.match(agreement_id):
        raise ApiError(404, "not_found", "Agreement not found.")
    out = build(agreement_id)
    if out is None:
        raise ApiError(404, "not_found", "No document belongs to this agreement.")
    return out


@router.put("/contracts/{contract_id}/agreement")
def set_agreement(contract_id: str, body: AgreementMeta, request: Request):
    src = deps.get_source(contract_id)
    try:
        meta = agreements.set_meta(src.id, body.agreement_id, body.doc_type, body.date_signed, auth.actor(request))
    except agreements.AgreementError as e:
        raise ApiError(422, "invalid_agreement", str(e)) from None
    from backend.api import persistence
    persistence.flush_soon()
    return meta

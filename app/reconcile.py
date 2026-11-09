"""Current effective terms of ONE agreement after amendments. Plain Python, no model: the same discipline as penalty.py.

Input: the documents of one agreement (SPA, Addendum 1, Extension Letter, ...), each with a signing date and the terms it
STATES. A document that is silent on a term leaves the earlier value alone ("last writer wins": the latest-signed document that
mentions a term decides it). Output: the current state, where each value came from, and a timeline of what each document changed.

Terms tracked (what the extraction reads): price, possession_date, payment_schedule, penalty_rate (with its basis),
penalty_cap (percent of price) and grace_period_days.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from app.agreements import AMENDING_TYPES

FIELDS = ("price", "possession_date", "payment_schedule", "penalty_rate", "penalty_cap", "grace_period_days")
_TYPE_ORDER = {t: i for i, t in enumerate(AMENDING_TYPES)}          # on the same day: SPA, then addenda, then extension letters


@dataclass(frozen=True)
class Doc:
    doc_id: str
    name: str
    doc_type: str
    date_signed: Optional[date]
    fields: dict[str, Any] = field(default_factory=dict)             # only the terms this document STATES (absent = silent)


def fields_from_contract(c) -> dict[str, Any]:
    """The terms an extracted document states, as plain JSON-safe values. A term the document does not state is left out."""
    out: dict[str, Any] = {}
    if c.price.value is not None:
        out["price"] = float(c.price.value)
    if c.handover_date.value is not None:
        out["possession_date"] = c.handover_date.value.isoformat()
    if c.payment_plan:
        out["payment_schedule"] = [{"name": m.name, "percent": float(m.percent),
                                    "due_date": m.due_date.isoformat() if m.due_date else None} for m in c.payment_plan]
    if c.delay_rate.value is not None:
        out["penalty_rate"] = {"rate": float(c.delay_rate.value), "basis": c.delay_basis.value}
    if c.delay_cap.value is not None:
        out["penalty_cap"] = float(c.delay_cap.value)
    if c.grace_period_days.value is not None:
        out["grace_period_days"] = int(c.grace_period_days.value)
    return out


def reconcile(agreement_id: str, docs: list[Doc]) -> dict:
    problems: list[str] = []
    used: list[Doc] = []
    for d in docs:
        if d.doc_type not in AMENDING_TYPES:
            problems.append(f"{d.name}: a {d.doc_type} belongs to the project, not to one agreement, so it is not merged.")
        elif d.date_signed is None:
            problems.append(f"{d.name}: no signing date, so its place in the order is unknown and it is not merged.")
        else:
            used.append(d)
    used.sort(key=lambda d: (d.date_signed, _TYPE_ORDER[d.doc_type], d.name))

    current: dict[str, Any] = {}
    sources: dict[str, dict] = {}
    timeline: list[dict] = []
    plan_versions = 0
    for d in used:
        changes = []
        for f in FIELDS:
            if f not in d.fields:
                continue
            new, old = d.fields[f], current.get(f)
            if f in current and new == old:
                continue                                              # restated, nothing changed
            changes.append({"field": f, "kind": "changed" if f in current else "set", "from": old, "to": new})
            current[f] = new
            sources[f] = {"doc_id": d.doc_id, "name": d.name, "doc_type": d.doc_type, "date_signed": d.date_signed.isoformat()}
            if f == "payment_schedule":
                plan_versions += 1
        timeline.append({"date": d.date_signed.isoformat(), "doc_type": d.doc_type, "doc_id": d.doc_id, "name": d.name,
                         "changes": changes})
    return {
        "agreement_id": agreement_id,
        "documents": [{"doc_id": d.doc_id, "name": d.name, "doc_type": d.doc_type,
                       "date_signed": d.date_signed.isoformat() if d.date_signed else None} for d in docs],
        "current": current | {"payment_plan_version": max(plan_versions, 1)},
        "sources": sources,
        "missing": [f for f in FIELDS if f not in current],
        "timeline": timeline,
        "problems": problems,
    }

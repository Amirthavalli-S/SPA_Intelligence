"""Turn a golden labels.json into the tool input the extraction model would return, so the pipeline can run offline.

Used by tests and by scripts/seed_demo.py. It is NOT used by the app or by the accuracy evaluation, which always read the real model's output.
"""
from __future__ import annotations


def _s(x: dict | None) -> dict:
    x = x or {}
    return {"value": x.get("value"), "source_page": x.get("page"), "source_quote": x.get("quote")}


def labels_to_tool_input(labels: dict) -> dict:
    return {
        **{f: _s(labels.get(f)) for f in ("buyer", "unit_id", "price", "area_sqft", "handover_date", "grace_period_days",
                                          "delay_rate", "delay_basis", "delay_cap", "cancellation_clause")},
        "payment_plan": [{"name": m["name"], "percent": m["percent"], "due_date": m.get("due_date"), "trigger": m.get("trigger"),
                          "source_page": m["page"], "source_quote": m["quote"]} for m in labels.get("payment_plan", [])],
        "dated_clauses": [{"kind": d["kind"], "description": d["description"], "amount": d["amount"], "unit": d["unit"], "anchor": d["anchor"],
                           "source_page": d["page"], "source_quote": d["quote"]} for d in labels.get("dated_clauses", [])],
    }

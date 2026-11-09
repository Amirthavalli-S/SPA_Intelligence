"""Wires the database into the running API: restore at startup, save in the background, keep the contracts table current.

With DATABASE_URL unset every function here is a no-op and the app runs on local files as before.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from app import config, db
from app.mirror import Mirror

log = logging.getLogger("spa.persistence")
_mirror: Mirror | None = None
_state = {"enabled": False, "ok": None, "restored": 0, "error": None}


def _roots() -> tuple[dict[str, Path], tuple[str, ...]]:
    from app.notifiers import _state_path
    roots = {"uploads": config.UPLOAD_DIR, "cache": config.CACHE_DIR, "reviews": config.REVIEW_DIR,
             "docsets": config.UPLOAD_DIR.parent / "docsets", "agreements": config.AGREEMENT_DIR, "alerts": config.ALERTS_PATH, "notify": _state_path()}
    return roots, ("alerts", "notify")


def init() -> None:
    """Called once at startup. Never raises: if the database is unreachable the app runs on local files and says so in /api/health."""
    global _mirror
    _state.update(enabled=db.enabled(), ok=None, restored=0, error=None)
    if not db.enabled():
        return
    try:
        if os.environ.get("DB_AUTO_MIGRATE", "1") != "0":
            db.migrate()
        roots, file_kinds = _roots()
        _mirror = Mirror(roots, file_kinds)
        _mirror.on_change = lambda n: sync_contracts()
        _state["restored"] = _mirror.hydrate()
        _mirror.flush()                                   # push anything that exists locally but not yet in the database
        sync_contracts()
        _mirror.start(float(os.environ.get("DB_SYNC_SECONDS") or 10))
        _state["ok"] = True
        log.info("database connected (%s); restored %d files", db.describe(), _state["restored"])
    except Exception as e:  # noqa: BLE001
        _state.update(ok=False, error=f"{type(e).__name__}: {str(e)[:160]}")
        log.error("database unavailable, running on local files: %s", _state["error"])


def shutdown() -> None:
    if _mirror is not None:
        _mirror.stop()
    db.close()


def flush_soon() -> None:
    """Save changes now, without making the caller wait."""
    if _mirror is not None:
        threading.Thread(target=_mirror.flush, daemon=True, name="spa-flush").start()


def sync_contracts() -> None:
    """Refresh the readable `contracts` table from the registry. Best effort."""
    if not db.enabled():
        return
    import json
    from backend.api import deps
    from app import agreements
    from app.review import is_approved, last_reviewer, load_store, review_items
    rows, approved, unapproved, agreement_ids = [], [], [], set()
    for s in deps.list_sources():
        status, _ = deps.status_for(s)
        eff = deps.effective_contract(s) if status == "extracted" else None
        open_items = len(review_items(eff)) if eff else 0
        up = None
        meta = s.path.with_suffix(".meta.json")
        if s.kind == "upload" and meta.exists():
            up = json.loads(meta.read_text()).get("uploaded_at")
        am = agreements.get(s.id, s.name)
        rows.append((s.id, s.name, s.kind, s.pages, s.size, status, eff.model if eff else None,
                     eff.extracted_at if eff else None, open_items, up, am["agreement_id"], am["doc_type"], am["date_signed"]))
        if am["agreement_id"]:
            agreement_ids.add(am["agreement_id"])
        if eff is not None and is_approved(eff):                 # reviewed (or nothing flagged): the only data that becomes "official"
            who = last_reviewer(load_store(s.id)) or "automatic (nothing was flagged)"
            approved.append((s.id, s.name, who, json.dumps(eff.model_dump(mode="json"), default=str)))
        else:
            unapproved.append(s.id)                              # new draft, re-extracted, or a decision was removed: no longer official
    try:
        with db.connection() as cx:
            for r in rows:
                cx.execute(
                    "insert into contracts (id, name, kind, pages, size_bytes, status, model, extracted_at, review_open, uploaded_at, "
                    "agreement_id, doc_type, date_signed) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (id) do update set name = excluded.name, "
                    "pages = excluded.pages, size_bytes = excluded.size_bytes, status = excluded.status, model = excluded.model, "
                    "extracted_at = excluded.extracted_at, review_open = excluded.review_open, agreement_id = excluded.agreement_id, "
                    "doc_type = excluded.doc_type, date_signed = excluded.date_signed, updated_at = now()", r)
            for cid, name, who, data in approved:
                cx.execute(
                    "insert into approved_contracts (contract_id, name, approved_by, data) values (%s,%s,%s,%s::jsonb) "
                    "on conflict (contract_id) do update set name = excluded.name, approved_by = excluded.approved_by, "
                    "approved_at = case when approved_contracts.data is distinct from excluded.data then now() else approved_contracts.approved_at end, "
                    "data = excluded.data", (cid, name, who, data))
            if unapproved:
                cx.execute("delete from approved_contracts where contract_id = any(%s)", (unapproved,))
            _sync_effective(cx, agreement_ids)
    except Exception as e:  # noqa: BLE001
        log.warning("contracts sync failed: %s", type(e).__name__)


def _sync_effective(cx, agreement_ids: set[str]) -> None:
    """Keep effective_contracts equal to what reconcile computes from each agreement's documents (and drop agreements with none)."""
    import json
    from backend.api.routes.reconcile import build
    keep = []
    for aid in sorted(agreement_ids):
        r = build(aid)
        if r is None:
            continue
        keep.append(aid)
        c, rate = r["current"], r["current"].get("penalty_rate") or {}
        cx.execute(
            "insert into effective_contracts (agreement_id, price, possession_date, payment_plan_version, penalty_rate_per_sqft, "
            "penalty_basis, penalty_cap_pct, grace_period_days, documents, timeline, pending_review, source_note) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) on conflict (agreement_id) do update set price = excluded.price, "
            "possession_date = excluded.possession_date, payment_plan_version = excluded.payment_plan_version, "
            "penalty_rate_per_sqft = excluded.penalty_rate_per_sqft, penalty_basis = excluded.penalty_basis, "
            "penalty_cap_pct = excluded.penalty_cap_pct, grace_period_days = excluded.grace_period_days, documents = excluded.documents, "
            "timeline = excluded.timeline, pending_review = excluded.pending_review, source_note = excluded.source_note, updated_at = now()",
            (aid, c.get("price"), c.get("possession_date"), c["payment_plan_version"], rate.get("rate"), rate.get("basis"),
             c.get("penalty_cap"), c.get("grace_period_days"), json.dumps(r["documents"]), json.dumps(r["timeline"]),
             r["pending_review"], "; ".join(r["problems"])[:500] or None))
    cx.execute("delete from effective_contracts where not (agreement_id = any(%s))", (keep,))


def status() -> dict:
    if not _state["enabled"]:
        return {"enabled": False}
    out = {"enabled": True, "ok": bool(_state["ok"]) and (_mirror.last_error is None if _mirror else False)}
    if _mirror and _mirror.last_flush:
        out["last_sync_age_s"] = int(__import__("time").time() - _mirror.last_flush)
    return out
